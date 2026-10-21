"""LangGraph investigation workflow implementation."""

import json
import logging
from typing import Any
from langgraph.graph import StateGraph, END

from incidentiq.agents.state import InvestigationState
from incidentiq.agents.output import validate_report_evidence
from incidentiq.retrieval.search import search_runbooks
from services.mcp_server.tools.dependencies import get_service_dependencies_impl
from incidentiq.models.provider import call_llm_or_baseline_reasoner
from incidentiq.db.session import SessionLocal
from incidentiq.db.models import Incident, IncidentEvent, InvestigationJob, InvestigationFinding
from incidentiq.storage.s3 import s3_service

logger = logging.getLogger("incidentiq.investigation.graph")


# --- Graph Nodes ---

def load_evidence(state: InvestigationState) -> dict[str, Any]:
    """Node 1: Fetch event records and relevant incident metadata."""
    incident_id = state.get("incident_id")
    events = state.get("events") or []

    # If events were not passed in state, load them from PostgreSQL
    if not events and incident_id:
        with SessionLocal() as db:
            inc = db.query(Incident).filter(Incident.id == incident_id).first()
            if inc:
                state["incident_title"] = inc.title
                state["service_name"] = inc.service_name
                state["severity"] = inc.severity

            db_events = db.query(IncidentEvent).filter(IncidentEvent.incident_id == incident_id).all()
            events = [
                {
                    "event_id": e.source_event_id,
                    "service": e.service_name,
                    "event_type": e.event_type,
                    "occurred_at": str(e.occurred_at),
                    "attributes": e.payload,
                }
                for e in db_events
            ]

    return {
        "events": events,
        "incident_title": state.get("incident_title", "Unknown Incident"),
        "service_name": state.get("service_name", "unknown"),
        "severity": state.get("severity", "medium"),
    }


def retrieve_runbooks(state: InvestigationState) -> dict[str, Any]:
    """Node 2: Retrieve relevant runbook chunks from pgvector."""
    query = f"{state.get('incident_title', '')} {state.get('service_name', '')}"
    # Add error messages from events to enhance semantic retrieval
    event_msgs = " ".join([e.get("message", "") for e in state.get("events", []) if isinstance(e, dict)])
    search_query = f"{query} {event_msgs}".strip()

    try:
        chunks = search_runbooks(query=search_query, top_k=3)
    except Exception as e:
        logger.warning(f"Error during runbook retrieval: {e}")
        chunks = []

    return {"runbook_chunks": chunks}


def inspect_dependencies(state: InvestigationState) -> dict[str, Any]:
    """Node 3: Call MCP tool to inspect service dependency topology from Neo4j."""
    service_name = state.get("service_name", "checkout")
    try:
        deps = get_service_dependencies_impl(service_name=service_name, depth=2)
    except Exception as e:
        logger.warning(f"MCP tool call failed: {e}")
        deps = {"root_service": service_name, "dependencies": [], "dependency_count": 0}

    return {"dependency_graph": deps}


def correlate_events(state: InvestigationState) -> dict[str, Any]:
    """Node 4: Identify temporal patterns and correlated signals using deterministic Python rules."""
    events = state.get("events", [])
    # Sort events temporally if timestamps are available
    sorted_events = sorted(events, key=lambda x: str(x.get("occurred_at", x.get("timestamp", ""))))
    return {"evidence": sorted_events}


def generate_hypotheses(state: InvestigationState) -> dict[str, Any]:
    """Node 5: Ask model / baseline reasoner for structured, evidence-referenced candidates."""
    report = call_llm_or_baseline_reasoner(
        incident_id=state.get("incident_id", ""),
        incident_title=state.get("incident_title", ""),
        service_name=state.get("service_name", ""),
        events=state.get("evidence", state.get("events", [])),
        runbook_chunks=state.get("runbook_chunks", []),
        dependency_graph=state.get("dependency_graph", {}),
    )
    return {"report": report}


def validate_report(state: InvestigationState) -> dict[str, Any]:
    """Node 6: Reject nonexistent event IDs, missing claims, invalid severity, and malformed output."""
    report = state.get("report", {})
    events = state.get("events", [])
    is_valid, validation_errors = validate_report_evidence(report, events)

    evidence_sufficient = is_valid and len(events) > 0 and report.get("root_cause", {}).get("confidence", 0) >= 0.5
    return {
        "evidence_sufficient": evidence_sufficient,
        "errors": validation_errors,
    }


def handle_uncertain_result(state: InvestigationState) -> dict[str, Any]:
    """Fallback node for inconclusive or uncertain investigations."""
    report = state.get("report", {})
    report["summary"] = "Inconclusive Investigation: Telemetry evidence was insufficient or references failed validation."
    if "root_cause" in report:
        report["root_cause"]["confidence"] = min(report["root_cause"].get("confidence", 0.5), 0.3)
    return {"report": report}


def persist_result(state: InvestigationState) -> dict[str, Any]:
    """Node 7: Save report and findings to PostgreSQL and MinIO, and mark job completed."""
    incident_id = state.get("incident_id")
    job_id = state.get("job_id")
    report = state.get("report", {})

    if incident_id and job_id:
        # 1. Upload report artifact to S3 (Blueprint layout: incidents/{incident_id}/reports/report.json)
        s3_key = f"incidents/{incident_id}/reports/report.json"
        try:
            s3_service.client.put_object(
                Bucket=s3_service.bucket_name,
                Key=s3_key,
                Body=json.dumps(report, indent=2).encode("utf-8"),
                ContentType="application/json",
            )
        except Exception as e:
            logger.error(f"Failed to upload report to S3: {e}")

        # 2. Persist findings into PostgreSQL
        with SessionLocal() as db:
            job = db.query(InvestigationJob).filter(InvestigationJob.id == job_id).first()
            if job:
                root_cause = report.get("root_cause", {})
                finding = InvestigationFinding(
                    job_id=job_id,
                    finding_type="root_cause",
                    claim=root_cause.get("claim", "Unknown"),
                    confidence=root_cause.get("confidence", 0.0),
                    evidence=root_cause.get("evidence_ids", []),
                )
                db.add(finding)
                job.status = "completed"
                db.commit()
            else:
                logger.info(f"Job {job_id} not in investigation_jobs table; skipped DB finding persist.")

    return {"report": report}


# --- Routing & Graph Construction ---

def check_sufficiency(state: InvestigationState) -> str:
    """Conditional router based on evidence sufficiency."""
    if state.get("evidence_sufficient", False):
        return "persist_result"
    return "handle_uncertain_result"


def build_investigation_graph():
    """Build the compiled LangGraph investigation workflow."""
    workflow = StateGraph(InvestigationState)

    # Add Nodes
    workflow.add_node("load_evidence", load_evidence)
    workflow.add_node("retrieve_runbooks", retrieve_runbooks)
    workflow.add_node("inspect_dependencies", inspect_dependencies)
    workflow.add_node("correlate_events", correlate_events)
    workflow.add_node("generate_hypotheses", generate_hypotheses)
    workflow.add_node("validate_report", validate_report)
    workflow.add_node("handle_uncertain_result", handle_uncertain_result)
    workflow.add_node("persist_result", persist_result)

    # Set Entry Point
    workflow.set_entry_point("load_evidence")

    # Add Edges
    workflow.add_edge("load_evidence", "retrieve_runbooks")
    workflow.add_edge("retrieve_runbooks", "inspect_dependencies")
    workflow.add_edge("inspect_dependencies", "correlate_events")
    workflow.add_edge("correlate_events", "generate_hypotheses")
    workflow.add_edge("generate_hypotheses", "validate_report")

    # Conditional branching
    workflow.add_conditional_edges(
        "validate_report",
        check_sufficiency,
        {
            "persist_result": "persist_result",
            "handle_uncertain_result": "handle_uncertain_result",
        },
    )

    workflow.add_edge("handle_uncertain_result", "persist_result")
    workflow.add_edge("persist_result", END)

    return workflow.compile()


investigation_graph = build_investigation_graph()
