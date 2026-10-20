"""Test end-to-end data flow: Publish to Kafka -> Consume -> Persist in PostgreSQL & Upload to S3."""

import sys
from pathlib import Path
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

load_dotenv()

from incidentiq.events.schemas import TelemetryEvent, IncidentNotification
from incidentiq.events.producer import event_producer
from incidentiq.storage.s3 import s3_service
from incidentiq.db.session import SessionLocal
from incidentiq.db.models import Incident, IncidentEvent, InvestigationJob
from services.worker.consumer import consume_one_notification


def run_data_flow_test():
    print("\n--- Day 1 Milestone 1: Verifying End-to-End Data Flow ---")

    # 1. Create a synthetic incident and event matching blueprint Page 6 contract
    incident_id = uuid.uuid4()
    job_id = uuid.uuid4()
    source_event_id = f"evt-{uuid.uuid4().hex[:6]}"

    event = TelemetryEvent(
        event_id=source_event_id,
        timestamp=datetime.now(timezone.utc),
        service="checkout",
        event_type="error",
        severity="high",
        message="Database request timed out",
        attributes={
            "database": "orders-db",
            "duration_ms": 3200,
            "deployment_version": "v1.4.2",
        },
    )

    notification = IncidentNotification(
        incident_id=incident_id,
        job_id=job_id,
        title="Checkout service latency spike and database timeouts",
        service_name="checkout",
        severity="high",
        started_at=datetime.now(timezone.utc),
        events=[event],
    )

    # 2. Publish to Kafka
    print(f"[1/4] Publishing incident notification {incident_id} to Kafka topic...", end=" ")
    event_producer.publish_incident_notification(notification)
    print("SUCCESS")

    # 3. Consume from Kafka and process
    print("[2/4] Consuming and processing event from Kafka...", end=" ")
    consumer_group = f"verify-group-{uuid.uuid4().hex[:6]}"
    result = consume_one_notification(group_id=consumer_group)
    if not result:
        print("FAILED: No message consumed from Kafka")
        sys.exit(1)
    print(f"SUCCESS (Processed {result['events_count']} event, S3 Key: {result['s3_key']})")

    # 4. Verify PostgreSQL persistence
    print("[3/4] Verifying record persistence in PostgreSQL...", end=" ")
    with SessionLocal() as db:
        db_incident = db.query(Incident).filter(Incident.id == incident_id).first()
        db_job = db.query(InvestigationJob).filter(InvestigationJob.incident_id == incident_id).first()
        db_event = db.query(IncidentEvent).filter(IncidentEvent.incident_id == incident_id).first()

        assert db_incident is not None, "Incident not found in PostgreSQL"
        assert db_job is not None, "Investigation job not found in PostgreSQL"
        assert db_event is not None, "IncidentEvent not found in PostgreSQL"
        assert db_event.source_event_id == source_event_id, "Source event ID mismatch"
        assert db_event.s3_key == result["s3_key"], "S3 key reference mismatch"
        print("SUCCESS (Incident, Job, and Event records verified in DB)")

    # 5. Verify S3 raw artifact storage
    print(f"[4/4] Verifying raw event JSONL artifact in MinIO ({result['s3_key']})...", end=" ")
    raw_events = s3_service.get_raw_events(result["s3_key"])
    assert len(raw_events) == 1, f"Expected 1 event in S3 JSONL, got {len(raw_events)}"
    assert raw_events[0]["event_id"] == source_event_id, "Event ID in S3 does not match"
    assert raw_events[0]["attributes"]["database"] == "orders-db", "Payload attributes mismatch in S3"
    print("SUCCESS (Raw JSONL artifact verified in S3)")

    print("\nData flow milestone verified! Events persisted in PostgreSQL and raw artifact stored in S3.\n")


if __name__ == "__main__":
    try:
        run_data_flow_test()
    finally:
        event_producer.close()
