"""Data access repositories keeping database queries separate from API routes."""

import json
from uuid import UUID
from typing import Any
from sqlalchemy.orm import Session
from incidentiq.db.models import Incident, InvestigationJob, InvestigationFinding, IncidentEvent
from incidentiq.storage.s3 import s3_service


class IncidentRepository:
    @staticmethod
    def get_incident(db: Session, incident_id: UUID) -> Incident | None:
        """Fetch incident record by ID."""
        return db.query(Incident).filter(Incident.id == incident_id).first()

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
        root_cause_finding = next((f for f in findings if f.finding_type == "root_cause"), None)

        if not root_cause_finding:
            return None

        return {
            "incident_id": str(incident_id),
            "summary": f"Investigation for {inc.title}",
            "root_cause": {
                "claim": root_cause_finding.claim,
                "confidence": root_cause_finding.confidence,
                "evidence_ids": root_cause_finding.evidence if isinstance(root_cause_finding.evidence, list) else [],
            },
            "affected_services": [inc.service_name],
            "alternatives": [],
            "recommended_checks": [],
            "limitations": [],
        }


incident_repository = IncidentRepository()
