"""Investigation runner executing the LangGraph agent with bounded retries and failed-job tracking."""

import logging
import time
from typing import Any
from datetime import datetime, timezone
from incidentiq.agents.graph import investigation_graph
from incidentiq.agents.state import InvestigationState
from incidentiq.db.session import SessionLocal
from incidentiq.db.models import Incident, InvestigationJob, IncidentEvent

logger = logging.getLogger("incidentiq.worker.runner")

MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 0.5


def run_investigation_job(
    incident_id: str,
    job_id: str,
    max_retries: int = MAX_RETRIES,
    initial_backoff: float = INITIAL_BACKOFF_SECONDS,
    workflow_invoker: Any = None,
) -> dict[str, Any]:
    """Execute the LangGraph investigation workflow with bounded retries and visible failure tracking."""
    attempt = 0
    last_error: Exception | None = None

    while attempt < max_retries:
        attempt += 1
        with SessionLocal() as db:
            job = db.query(InvestigationJob).filter(InvestigationJob.id == job_id).first()
            if not job:
                raise ValueError(f"Investigation job {job_id} not found in database")

            job.status = "running"
            job.started_at = job.started_at or datetime.now(timezone.utc)
            job.attempt_count = attempt
            db.commit()

            inc = db.query(Incident).filter(Incident.id == incident_id).first()
            if not inc:
                err_msg = f"Incident {incident_id} not found in database"
                job.status = "failed"
                job.error_message = err_msg
                job.finished_at = datetime.now(timezone.utc)
                db.commit()
                raise ValueError(err_msg)

            # Fetch structured incident events
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

        # Initialize workflow state
        state: InvestigationState = {
            "incident_id": str(incident_id),
            "job_id": str(job_id),
            "incident_title": inc.title,
            "service_name": inc.service_name,
            "severity": inc.severity,
            "events": events,
            "retry_count": attempt - 1,
        }

        try:
            logger.info(f"Executing investigation workflow for incident {incident_id} (job {job_id}, attempt {attempt}/{max_retries})")
            invoker = workflow_invoker or investigation_graph.invoke
            final_state = invoker(state)
            
            with SessionLocal() as db:
                job = db.query(InvestigationJob).filter(InvestigationJob.id == job_id).first()
                if job:
                    job.status = "completed"
                    job.finished_at = datetime.now(timezone.utc)
                    job.error_message = None

                inc = db.query(Incident).filter(Incident.id == incident_id).first()
                if inc:
                    inc.status = "resolved"

                db.commit()

            logger.info(f"Investigation completed successfully for incident {incident_id}")
            return final_state.get("report", {})

        except Exception as e:
            last_error = e
            logger.warning(f"Attempt {attempt}/{max_retries} failed for job {job_id}: {e}")
            if attempt < max_retries:
                time.sleep(initial_backoff * (2 ** (attempt - 1)))

    # Terminal failure after bounded retries: record actionable error
    with SessionLocal() as db:
        job = db.query(InvestigationJob).filter(InvestigationJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = f"Terminal failure after {max_retries} attempts: {str(last_error)}"
            job.finished_at = datetime.now(timezone.utc)
            db.commit()

    logger.error(f"Investigation job {job_id} marked as failed: {last_error}")
    raise RuntimeError(f"Investigation job {job_id} failed permanently: {last_error}")
