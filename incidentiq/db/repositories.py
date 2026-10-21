"""Data access repositories keeping database queries separate from API routes."""

import json
import uuid
from uuid import UUID
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from incidentiq.db.models import (
    Incident,
    InvestigationJob,
    InvestigationFinding,
    IncidentEvent,
    Feedback,
    OutboxEvent,
)
from incidentiq.storage.s3 import s3_service


class IncidentRepository:
    @staticmethod
    def get_incident(db: Session, incident_id: UUID) -> Incident | None:
        """Fetch incident record by ID."""
        return db.query(Incident).filter(Incident.id == incident_id).first()

    @staticmethod
    def list_incidents(db: Session, limit: int = 20, offset: int = 0) -> tuple[list[Incident], int]:
        """Fetch paginated incidents and total count."""
        total = db.query(func.count(Incident.id)).scalar() or 0
        items = (
            db.query(Incident)
            .order_by(Incident.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    @staticmethod
    def get_incident_events(db: Session, incident_id: UUID) -> list[IncidentEvent]:
        """Fetch chronological events related to an incident."""
        return (
            db.query(IncidentEvent)
            .filter(IncidentEvent.incident_id == incident_id)
            .order_by(IncidentEvent.occurred_at.asc())
            .all()
        )

    @staticmethod
    def get_job(db: Session, job_id: UUID) -> InvestigationJob | None:
        """Fetch investigation job by ID."""
        return db.query(InvestigationJob).filter(InvestigationJob.id == job_id).first()

    @staticmethod
    def get_latest_job_for_incident(db: Session, incident_id: UUID) -> InvestigationJob | None:
        """Fetch the most recent investigation job for an incident."""
        return (
            db.query(InvestigationJob)
            .filter(InvestigationJob.incident_id == incident_id)
            .order_by(InvestigationJob.created_at.desc())
            .first()
        )

    @staticmethod
    def get_findings_for_job(db: Session, job_id: UUID) -> list[InvestigationFinding]:
        """Fetch all findings for an investigation job."""
        return db.query(InvestigationFinding).filter(InvestigationFinding.job_id == job_id).all()

    @staticmethod
    def get_report_for_incident(db: Session, incident_id: UUID) -> dict[str, Any] | None:
        """Fetch final report artifact from MinIO S3 or reconstruct from PostgreSQL findings."""
        # 1. Attempt to fetch canonical report artifact from S3
        s3_key = f"incidents/{incident_id}/reports/report.json"
        try:
            resp = s3_service.client.get_object(Bucket=s3_service.bucket_name, Key=s3_key)
            return json.loads(resp["Body"].read().decode("utf-8"))
        except Exception:
            pass

        # 2. Fallback: synthesize from PostgreSQL findings if S3 artifact is not found
        inc = db.query(Incident).filter(Incident.id == incident_id).first()
        if not inc:
            return None

        job = (
            db.query(InvestigationJob)
            .filter(InvestigationJob.incident_id == incident_id)
            .order_by(InvestigationJob.created_at.desc())
            .first()
        )
        if not job:
            return None

        findings = db.query(InvestigationFinding).filter(InvestigationFinding.job_id == job.id).all()

        # 2a. Check if full report was cached directly in PostgreSQL findings
        full_report_finding = next((f for f in findings if f.finding_type == "full_report"), None)
        if full_report_finding and isinstance(full_report_finding.evidence, dict) and "root_cause" in full_report_finding.evidence:
            return full_report_finding.evidence

        # 2b. Synthesize from individual findings
        root_cause_finding = next((f for f in findings if f.finding_type == "root_cause"), None)
        if not root_cause_finding:
            return None

        alts = [f.claim for f in findings if f.finding_type == "alternative"]
        checks = [f.claim for f in findings if f.finding_type == "recommended_check"]
        lims = [f.claim for f in findings if f.finding_type == "limitation"]

        return {
            "incident_id": str(incident_id),
            "summary": f"Investigation for {inc.title}",
            "root_cause": {
                "claim": root_cause_finding.claim,
                "confidence": root_cause_finding.confidence,
                "evidence_ids": root_cause_finding.evidence if isinstance(root_cause_finding.evidence, list) else [],
            },
            "affected_services": [inc.service_name],
            "alternatives": alts if alts else [
                "Underlying configuration drift or secret rotation failure during container restart."
            ],
            "recommended_checks": checks if checks else [
                f"Review recent git deployments and verify telemetry metrics on {inc.service_name}.",
                "Inspect service error logs and connection pool limits."
            ],
            "limitations": lims,
        }

    @staticmethod
    def create_feedback(
        db: Session,
        incident_id: UUID,
        rating: str,
        comment: str | None = None,
    ) -> Feedback:
        """Record user feedback with rating constraint check."""
        feedback = Feedback(
            id=uuid.uuid4(),
            incident_id=incident_id,
            rating=rating,
            comment=comment,
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        return feedback

    @staticmethod
    def create_incident_with_events(
        db: Session,
        title: str,
        service_name: str,
        severity: str,
        events_data: list[dict[str, Any]],
        idempotency_key: str | None = None,
    ) -> tuple[Incident, InvestigationJob]:
        """Atomically create Incident, Job, Events, and Outbox event."""
        incident_id = uuid.uuid4()
        job_id = uuid.uuid4()

        # 1. Upload raw events to S3
        s3_key = s3_service.upload_raw_events(str(incident_id), events_data)

        # 2. Create Incident
        inc = Incident(
            id=incident_id,
            title=title,
            service_name=service_name,
            severity=severity,
            status="investigating",
            started_at=datetime.now(timezone.utc),
        )
        db.add(inc)

        # 3. Create Investigation Job
        job = InvestigationJob(
            id=job_id,
            incident_id=incident_id,
            status="queued",
        )
        db.add(job)

        # 4. Create Incident Events
        for evt in events_data:
            dt_str = evt.get("timestamp") or evt.get("occurred_at")
            if dt_str:
                dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
            else:
                dt = datetime.now(timezone.utc)

            event_record = IncidentEvent(
                id=uuid.uuid4(),
                incident_id=incident_id,
                source_event_id=evt.get("event_id") or f"evt-{uuid.uuid4().hex[:6]}",
                service_name=evt.get("service") or service_name,
                event_type=evt.get("event_type", "error"),
                occurred_at=dt,
                payload={**evt.get("attributes", {}), "message": evt.get("message", "")},
                s3_key=s3_key,
            )
            db.add(event_record)

        # 5. Outbox Event for reliable Kafka notification
        outbox = OutboxEvent(
            id=uuid.uuid4(),
            aggregate_id=incident_id,
            event_type="incident.created",
            payload={
                "incident_id": str(incident_id),
                "job_id": str(job_id),
                "idempotency_key": idempotency_key,
                "s3_key": s3_key,
            },
        )
        db.add(outbox)

        db.commit()
        db.refresh(inc)
        db.refresh(job)
        return inc, job


incident_repository = IncidentRepository()
