"""Investigation Job polling API route."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from services.api.dependencies import get_db
from incidentiq.db.repositories import incident_repository
from services.api.schemas.reports import JobStatusResponse

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/{id}", response_model=JobStatusResponse)
def get_job_status(id: UUID, db: Session = Depends(get_db)) -> JobStatusResponse:
    """Poll investigation status for a given job ID."""
    job = incident_repository.get_job(db, id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {id} not found")
    return JobStatusResponse(
        job_id=job.id,
        incident_id=job.incident_id,
        status=job.status,
        attempt_count=job.attempt_count,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error_message=job.error_message,
    )
