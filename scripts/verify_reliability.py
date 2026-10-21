"""Verification script for Day 4 Task 1: Reliability & Failure Handling.

Validates:
1. Duplicate Kafka / telemetry event delivery idempotency (no duplicate incidents, jobs, or events).
2. Idempotent finding persistence (no duplicate findings on workflow reruns).
3. Bounded retries with exponential backoff on transient failure, recovering to 'completed'.
4. Bounded retries on permanent failure, marking job 'failed' with visible error_message and finished_at.
"""

import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

from incidentiq.db.session import SessionLocal
from incidentiq.db.models import Incident, InvestigationJob, IncidentEvent, InvestigationFinding
from services.worker.consumer import process_incident_notification
from services.worker.runner import run_investigation_job


def test_duplicate_event_deduplication():
    print("\n[1/4] Testing Duplicate Event Delivery Idempotency...")
    incident_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    
    payload = {
        "incident_id": incident_id,
        "job_id": job_id,
        "title": "Idempotency Test Outage",
        "service_name": "checkout",
        "severity": "high",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "events": [
            {
                "event_id": f"evt-dup-1-{incident_id[:6]}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": "checkout",
                "event_type": "error",
                "severity": "high",
                "message": "Connection timeout",
                "attributes": {"source": "test"},
            },
            {
                "event_id": f"evt-dup-2-{incident_id[:6]}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": "checkout",
                "event_type": "warning",
                "severity": "medium",
                "message": "High latency detected",
                "attributes": {"source": "test"},
            },
        ],
    }

    # First delivery
    with SessionLocal() as db:
        res1 = process_incident_notification(db, payload)
    
    with SessionLocal() as db:
        inc_count_1 = db.query(Incident).filter(Incident.id == incident_id).count()
        job_count_1 = db.query(InvestigationJob).filter(InvestigationJob.id == job_id).count()
        evt_count_1 = db.query(IncidentEvent).filter(IncidentEvent.incident_id == incident_id).count()
        assert inc_count_1 == 1, f"Expected 1 incident, got {inc_count_1}"
        assert job_count_1 == 1, f"Expected 1 job, got {job_count_1}"
        assert evt_count_1 == 2, f"Expected 2 events, got {evt_count_1}"

    # Duplicate delivery (replay of identical message)
    with SessionLocal() as db:
        res2 = process_incident_notification(db, payload)

    with SessionLocal() as db:
        inc_count_2 = db.query(Incident).filter(Incident.id == incident_id).count()
        job_count_2 = db.query(InvestigationJob).filter(InvestigationJob.id == job_id).count()
        evt_count_2 = db.query(IncidentEvent).filter(IncidentEvent.incident_id == incident_id).count()
        assert inc_count_2 == 1, f"Duplicate created incident! Count: {inc_count_2}"
        assert job_count_2 == 1, f"Duplicate created job! Count: {job_count_2}"
        assert evt_count_2 == 2, f"Duplicate created events! Count: {evt_count_2}"

    print("  -> SUCCESS: Duplicate message replay correctly preserved exact single copies of Incident, Job, and Events.")
    return incident_id, job_id


def test_idempotent_findings_persistence(incident_id: str, job_id: str):
    print("\n[2/4] Testing Idempotent Investigation Findings Persistence...")
    # Run the investigation workflow for this incident
    report1 = run_investigation_job(incident_id, job_id)
    
    with SessionLocal() as db:
        findings_count_1 = db.query(InvestigationFinding).filter(InvestigationFinding.job_id == job_id).count()
        assert findings_count_1 == 1, f"Expected 1 finding, found {findings_count_1}"

    # Run the investigation workflow a second time for the same job (simulating retry or duplicate trigger)
    report2 = run_investigation_job(incident_id, job_id)

    with SessionLocal() as db:
        findings_count_2 = db.query(InvestigationFinding).filter(InvestigationFinding.job_id == job_id).count()
        assert findings_count_2 == 1, f"Rerun created duplicate findings! Count: {findings_count_2}"

    print("  -> SUCCESS: Multiple workflow executions on the same job updated finding in-place (no duplicate findings).")


def test_transient_failure_recovery():
    print("\n[3/4] Testing Bounded Retries with Transient Failure Recovery...")
    incident_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    
    payload = {
        "incident_id": incident_id,
        "job_id": job_id,
        "title": "Transient Failure Test",
        "service_name": "checkout",
        "severity": "medium",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "events": [],
    }
    with SessionLocal() as db:
        process_incident_notification(db, payload)

    calls = 0
    def flaky_workflow(state):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("Simulated temporary network blip to dependency")
        return {"report": {"summary": "Recovered after transient error", "root_cause": {"claim": "Recovered", "confidence": 0.9, "evidence_ids": []}}}

    # Execute with fast initial backoff for quick test execution
    report = run_investigation_job(
        incident_id=incident_id,
        job_id=job_id,
        max_retries=3,
        initial_backoff=0.05,
        workflow_invoker=flaky_workflow,
    )

    with SessionLocal() as db:
        job = db.query(InvestigationJob).filter(InvestigationJob.id == job_id).first()
        assert job.status == "completed", f"Expected job status 'completed', got '{job.status}'"
        assert job.attempt_count == 2, f"Expected 2 attempts, got {job.attempt_count}"
        assert job.error_message is None, f"Expected error_message to be cleared, got '{job.error_message}'"
        assert job.finished_at is not None, "Expected finished_at timestamp to be set"

    print(f"  -> SUCCESS: Transient failure triggered retry; successfully recovered on attempt {job.attempt_count}!")


def test_terminal_failure_handling():
    print("\n[4/4] Testing Bounded Retries Exhaustion & Visible Failed-Job State...")
    incident_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    
    payload = {
        "incident_id": incident_id,
        "job_id": job_id,
        "title": "Permanent Failure Test",
        "service_name": "checkout",
        "severity": "high",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "events": [],
    }
    with SessionLocal() as db:
        process_incident_notification(db, payload)

    calls = 0
    def failing_workflow(state):
        nonlocal calls
        calls += 1
        raise ValueError(f"Deterministic LLM output schema rejection on attempt {calls}")

    failed = False
    try:
        run_investigation_job(
            incident_id=incident_id,
            job_id=job_id,
            max_retries=3,
            initial_backoff=0.05,
            workflow_invoker=failing_workflow,
        )
    except RuntimeError as e:
        failed = True
        print(f"  -> Captured expected permanent failure exception: {e}")

    assert failed, "Expected run_investigation_job to raise RuntimeError on terminal failure"

    with SessionLocal() as db:
        job = db.query(InvestigationJob).filter(InvestigationJob.id == job_id).first()
        assert job.status == "failed", f"Expected job status 'failed', got '{job.status}'"
        assert job.attempt_count == 3, f"Expected attempt_count 3, got {job.attempt_count}"
        assert job.finished_at is not None, "Expected finished_at timestamp to be populated"
        assert job.error_message and "Terminal failure after 3 attempts" in job.error_message, (
            f"Expected actionable error_message, got: {job.error_message}"
        )
        print(f"  -> Verified DB job status: '{job.status}', attempt_count: {job.attempt_count}")
        print(f"  -> Verified actionable error_message: \"{job.error_message}\"")

    print("  -> SUCCESS: Bounded retry limit strictly enforced, job marked 'failed' with actionable diagnostics.")


def main():
    print("=" * 65)
    print(" Day 4 Task 1: Reliability, Retries & Idempotency Verification")
    print("=" * 65)
    try:
        inc_id, j_id = test_duplicate_event_deduplication()
        test_idempotent_findings_persistence(inc_id, j_id)
        test_transient_failure_recovery()
        test_terminal_failure_handling()
        print("\n" + "=" * 65)
        print(" ALL RELIABILITY AND FAILURE HANDLING TESTS PASSED!")
        print("=" * 65)
    except Exception as e:
        print(f"\nVerification FAILED: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
