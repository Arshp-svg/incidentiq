"""Investigation runner executing the LangGraph agent for a given incident."""

import logging
from typing import Any
from datetime import datetime, timezone
from incidentiq.agents.graph import investigation_graph
from incidentiq.agents.state import InvestigationState
from incidentiq.db.session import SessionLocal
from incidentiq.db.models import Incident, InvestigationJob, IncidentEvent

logger = logging.getLogger("incidentiq.worker.runner")


def run_investigation_job(incident_id: str, job_id: str) -> dict[str, Any]:
    """Execute the end-to-end LangGraph investigation workflow for a queued job."""
    with SessionLocal() as db:
        # 1. Update job status to 'running'
        job = db.query(InvestigationJob).filter(InvestigationJob.id == job_id).first()
        if job:
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            job.attempt_count += 1
            db.commit()

        # 2. Fetch incident details
        inc = db.query(Incident).filter(Incident.id == incident_id).first()
        if not inc:
            raise ValueError(f"Incident {incident_id} not found in database")

        # 3. Fetch structured incident events
        db_events = db.query(IncidentEvent).filter(IncidentEvent.incident_id == incident_id).all()
        events = [
            {
                "event_id": e.source_event_id,
                "service": e.service_name,
                "event_type": e.event_type,
                "occurred_at": str(e.occurred_at),
                "message": e.payload.get("message", e.event_type) if isinstance(e.payload, dict) else e.event_type,
                "attributes": e.payload,
            }
            for e in db_events
        ]

    # 4. Initialize workflow state
    state: InvestigationState = {
        "incident_id": str(incident_id),
        "job_id": str(job_id),
        "incident_title": inc.title,
        "service_name": inc.service_name,
        "severity": inc.severity,
        "events": events,
        "retry_count": 0,
    }

    # 5. Execute LangGraph workflow
    logger.info(f"Starting investigation workflow for incident {incident_id} (job {job_id})")
    final_state = investigation_graph.invoke(state)
    logger.info(f"Investigation completed for incident {incident_id}")

    return final_state.get("report", {})
