"""Kafka consumer worker for consuming incident notifications and persisting events."""

import json
import logging
from typing import Any
from uuid import UUID
from datetime import datetime, timezone
from kafka import KafkaConsumer
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from incidentiq.config import settings
from incidentiq.db.session import SessionLocal
from incidentiq.db.models import Incident, InvestigationJob, IncidentEvent
from incidentiq.events.schemas import IncidentNotification, TelemetryEvent
from incidentiq.storage.s3 import s3_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("incidentiq.worker.consumer")


def process_incident_notification(db: Session, data: dict[str, Any]) -> dict[str, Any]:
    """Process an incident notification: store raw events in S3, persist incident and events in DB."""
    notification = IncidentNotification.model_validate(data)
    incident_id = notification.incident_id

    # 1. Upload raw events to S3
    raw_event_dicts = [evt.model_dump(mode="json") for evt in notification.events]
    s3_key = s3_service.upload_raw_events(str(incident_id), raw_event_dicts)
    logger.info(f"Uploaded {len(raw_event_dicts)} raw events to S3 at {s3_key}")

    # 2. Persist Incident (idempotent upsert)
    stmt_incident = insert(Incident).values(
        id=incident_id,
        title=notification.title,
        service_name=notification.service_name,
        severity=notification.severity,
        status="open",
        started_at=notification.started_at,
    ).on_conflict_do_nothing(index_elements=["id"])
    db.execute(stmt_incident)

    # 3. Persist Investigation Job (idempotent upsert)
    stmt_job = insert(InvestigationJob).values(
        id=notification.job_id,
        incident_id=incident_id,
        status="queued",
        attempt_count=0,
    ).on_conflict_do_nothing(index_elements=["id"])
    db.execute(stmt_job)

    # 4. Persist structured IncidentEvents (idempotent upsert on (incident_id, source_event_id))
    for evt in notification.events:
        stmt_event = insert(IncidentEvent).values(
            incident_id=incident_id,
            source_event_id=evt.event_id,
            service_name=evt.service,
            event_type=evt.event_type,
            occurred_at=evt.timestamp,
            payload=evt.attributes,
            s3_key=s3_key,
        ).on_conflict_do_nothing(constraint="uq_incident_source_event")
        db.execute(stmt_event)

    db.commit()
    logger.info(f"Persisted incident {incident_id} and events in PostgreSQL")

    return {
        "incident_id": str(incident_id),
        "job_id": str(notification.job_id),
        "s3_key": s3_key,
        "events_count": len(notification.events),
    }


def create_kafka_consumer(group_id: str = "incidentiq-worker-group", auto_offset_reset: str = "earliest") -> KafkaConsumer:
    """Create a configured KafkaConsumer instance."""
    return KafkaConsumer(
        settings.KAFKA_TOPIC_INCIDENT_EVENTS,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        group_id=group_id,
        auto_offset_reset=auto_offset_reset,
        enable_auto_commit=True,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        consumer_timeout_ms=10000,
    )


def consume_one_notification(group_id: str = "incidentiq-worker-verify") -> dict[str, Any] | None:
    """Poll for a single notification from Kafka and process it."""
    consumer = create_kafka_consumer(group_id=group_id)
    try:
        records = consumer.poll(timeout_ms=10000, max_records=1)
        for topic_partition, messages in records.items():
            for message in messages:
                logger.info(f"Received message from Kafka topic {message.topic} partition {message.partition}")
                with SessionLocal() as db:
                    result = process_incident_notification(db, message.value)
                    return result
        return None
    finally:
        consumer.close()
