"""Integration tests for LangGraph investigation workflow, bounded retries, Neo4j MCP, and pgvector."""

import uuid
import pytest
from datetime import datetime, timezone

from incidentiq.db.session import SessionLocal
from incidentiq.db.models import Incident, InvestigationJob, IncidentEvent, InvestigationFinding
from incidentiq.retrieval.search import search_runbooks
from services.mcp_server.tools.dependencies import get_service_dependencies_impl
from services.worker.consumer import process_incident_notification
from services.worker.runner import run_investigation_job


def test_mcp_service_dependency_tool():
    """Verify MCP dependency traversal enforces depth boundaries and returns valid graph topology."""
    deps = get_service_dependencies_impl(service_name="checkout", depth=2)
    assert deps["root_service"] == "checkout"
    assert "dependencies" in deps
    assert deps["dependency_count"] > 0
    assert any(d["name"] == "orders" for d in deps["dependencies"])

    # Test depth boundary enforcement
    with pytest.raises(ValueError, match="depth must be between 1 and 3"):
        get_service_dependencies_impl(service_name="checkout", depth=4)

    with pytest.raises(ValueError, match="depth must be between 1 and 3"):
        get_service_dependencies_impl(service_name="checkout", depth=0)


def test_pgvector_runbook_search():
    """Verify pgvector semantic similarity search returns indexed runbook chunks."""
    results = search_runbooks(query="checkout orders-db database timeout", top_k=3)
    assert len(results) > 0
    doc_names = [r["document_name"] for r in results]
    assert "checkout_database_latency" in doc_names or "checkout_database_latency.md" in doc_names
    assert "content" in results[0]
    assert "similarity_score" in results[0]


def test_end_to_end_investigation_workflow_and_idempotency():
    """Verify complete investigation lifecycle and idempotent finding persistence."""
    incident_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    payload = {
        "incident_id": incident_id,
        "job_id": job_id,
        "title": "Integration Test Checkout DB Latency",
        "service_name": "checkout",
        "severity": "high",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "events": [
            {
                "event_id": f"evt-integ-1-{incident_id[:6]}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": "checkout",
                "event_type": "error",
                "severity": "high",
                "message": "Database request to orders-db timed out",
                "attributes": {"database": "orders-db", "duration_ms": 3200},
            },
            {
                "event_id": f"evt-integ-2-{incident_id[:6]}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": "orders-db",
                "event_type": "error",
                "severity": "high",
                "message": "Slow query detected on table orders",
                "attributes": {"database": "orders-db", "duration_ms": 4000},
            },
        ],
    }

    # Ingest notification
    with SessionLocal() as db:
        process_incident_notification(db, payload)

    # First workflow execution
    report1 = run_investigation_job(incident_id=incident_id, job_id=job_id)
    assert "root_cause" in report1
    assert report1["root_cause"]["claim"] != ""

    with SessionLocal() as db:
        job = db.query(InvestigationJob).filter(InvestigationJob.id == job_id).first()
        assert job.status == "completed"
        assert job.error_message is None
        findings_count = db.query(InvestigationFinding).filter(InvestigationFinding.job_id == job_id).count()
        assert findings_count == 1

    # Second workflow execution (verifying idempotent findings persistence)
    report2 = run_investigation_job(incident_id=incident_id, job_id=job_id)
    with SessionLocal() as db:
        findings_count_after = db.query(InvestigationFinding).filter(InvestigationFinding.job_id == job_id).count()
        assert findings_count_after == 1, "Duplicate findings were created on rerun!"


def test_bounded_retries_transient_and_terminal():
    """Verify bounded retry policy on transient failure and terminal failure state."""
    # 1. Transient recovery
    incident_id_trans = str(uuid.uuid4())
    job_id_trans = str(uuid.uuid4())
    with SessionLocal() as db:
        process_incident_notification(db, {
            "incident_id": incident_id_trans,
            "job_id": job_id_trans,
            "title": "Transient Fail Test",
            "service_name": "checkout",
            "severity": "medium",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "events": [],
        })

    attempts = 0
    def flaky_invoker(state):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionResetError("Simulated transient connection reset")
        return {"report": {"summary": "OK", "root_cause": {"claim": "Recovered", "confidence": 0.8, "evidence_ids": []}}}

    run_investigation_job(incident_id_trans, job_id_trans, max_retries=3, initial_backoff=0.01, workflow_invoker=flaky_invoker)
    with SessionLocal() as db:
        job_t = db.query(InvestigationJob).filter(InvestigationJob.id == job_id_trans).first()
        assert job_t.status == "completed"
        assert job_t.attempt_count == 2

    # 2. Terminal failure
    incident_id_term = str(uuid.uuid4())
    job_id_term = str(uuid.uuid4())
    with SessionLocal() as db:
        process_incident_notification(db, {
            "incident_id": incident_id_term,
            "job_id": job_id_term,
            "title": "Terminal Fail Test",
            "service_name": "checkout",
            "severity": "high",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "events": [],
        })

    def perm_failing_invoker(state):
        raise RuntimeError("Permanent schema constraint rejection")

    with pytest.raises(RuntimeError, match="failed permanently"):
        run_investigation_job(incident_id_term, job_id_term, max_retries=3, initial_backoff=0.01, workflow_invoker=perm_failing_invoker)

    with SessionLocal() as db:
        job_term = db.query(InvestigationJob).filter(InvestigationJob.id == job_id_term).first()
        assert job_term.status == "failed"
        assert job_term.attempt_count == 3
        assert "Terminal failure after 3 attempts" in job_term.error_message
        assert job_term.finished_at is not None
