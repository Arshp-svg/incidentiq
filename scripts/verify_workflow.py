"""Verify the LangGraph investigation workflow with typed state and evidence validation."""

import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

load_dotenv()

from datetime import datetime, timezone
from incidentiq.agents.graph import investigation_graph
from incidentiq.agents.state import InvestigationState
from incidentiq.agents.output import validate_report_evidence
from incidentiq.db.session import SessionLocal
from incidentiq.db.models import Incident, InvestigationJob, InvestigationFinding


def verify_workflow():
    print("\n--- Day 2 Task 3: Verifying LangGraph Workflow ---")

    # 1. Test standard incident with verifiable evidence
    print("[1/2] Executing workflow with synthetic checkout database failure...")
    incident_id = uuid.uuid4()
    job_id = uuid.uuid4()

    # Seed incident and job in PostgreSQL so DB findings and status updates are tested
    with SessionLocal() as db:
        inc = Incident(
            id=incident_id,
            title="Checkout latency surge and database timeouts",
            service_name="checkout",
            severity="high",
            started_at=datetime.now(timezone.utc),
        )
        job = InvestigationJob(
            id=job_id,
            incident_id=incident_id,
            status="queued",
        )
        db.add(inc)
        db.add(job)
        db.commit()

    synthetic_events = [
        {
            "event_id": "evt-chk-101",
            "service": "checkout",
            "event_type": "error",
            "message": "Database request timed out after 3200ms",
            "attributes": {"database": "orders-db", "query": "SELECT * FROM orders"},
        },
        {
            "event_id": "evt-chk-102",
            "service": "orders",
            "event_type": "warn",
            "message": "Database connection pool saturated",
            "attributes": {"database": "orders-db", "active_connections": 100},
        },
    ]

    initial_state: InvestigationState = {
        "incident_id": str(incident_id),
        "job_id": str(job_id),
        "incident_title": "Checkout latency surge and database timeouts",
        "service_name": "checkout",
        "severity": "high",
        "events": synthetic_events,
    }

    result = investigation_graph.invoke(initial_state)

    print("  Workflow executed successfully!")
    print(f"  - Retrieved Runbook Chunks: {len(result.get('runbook_chunks', []))}")
    print(f"  - Neo4j Dependency Count: {result.get('dependency_graph', {}).get('dependency_count', 0)}")
    print(f"  - Report Summary: {result.get('report', {}).get('summary')}")
    print(f"  - Root Cause Claim: {result.get('report', {}).get('root_cause', {}).get('claim')}")
    print(f"  - Cited Evidence IDs: {result.get('report', {}).get('root_cause', {}).get('evidence_ids')}")

    # Assertions on standard execution
    assert len(result.get("runbook_chunks", [])) > 0, "Expected retrieved runbooks"
    assert result.get("dependency_graph", {}).get("dependency_count", 0) > 0, "Expected Neo4j dependencies"

    # Verify DB persistence of finding and job completion
    with SessionLocal() as db:
        updated_job = db.query(InvestigationJob).filter(InvestigationJob.id == job_id).first()
        finding = db.query(InvestigationFinding).filter(InvestigationFinding.job_id == job_id).first()
        assert updated_job is not None and updated_job.status == "completed", "Job status was not set to completed"
        assert finding is not None, "Investigation finding was not persisted to PostgreSQL"
        print(f"  - Verified PostgreSQL Finding: claim='{finding.claim[:40]}...' (Job Status: {updated_job.status})")
    report = result.get("report", {})
    assert report, "Report was not generated"

    # Deterministic evidence check: every cited ID must exist in synthetic_events
    is_valid, errors = validate_report_evidence(report, synthetic_events)
    assert is_valid, f"Evidence validation failed: {errors}"
    assert result.get("evidence_sufficient") is True, "Evidence should be marked sufficient"

    # 2. Test abstention / insufficient evidence scenario
    print("\n[2/2] Executing workflow with empty events (abstention test)...")
    empty_state: InvestigationState = {
        "incident_id": str(uuid.uuid4()),
        "job_id": str(uuid.uuid4()),
        "incident_title": "Unclear alert with no logs",
        "service_name": "checkout",
        "severity": "low",
        "events": [],
    }

    empty_result = investigation_graph.invoke(empty_state)
    empty_report = empty_result.get("report", {})
    print(f"  - Abstention Report Summary: {empty_report.get('summary')}")
    print(f"  - Abstention Confidence: {empty_report.get('root_cause', {}).get('confidence')}")

    assert empty_result.get("evidence_sufficient") is False, "Empty events should be marked insufficient"
    assert "Inconclusive" in empty_report.get("summary", ""), "Expected inconclusive summary for empty events"

    print("\nLangGraph workflow with typed state and validation SUCCESSFUL!\n")


if __name__ == "__main__":
    verify_workflow()
