"""Incident and Report API routes."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from services.api.dependencies import get_db
from incidentiq.db.repositories import incident_repository
from services.api.schemas.reports import IncidentDetailResponse, ReportResponse

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


@router.get("/{id}", response_model=IncidentDetailResponse)
def get_incident(id: UUID, db: Session = Depends(get_db)) -> IncidentDetailResponse:
    """Fetch incident details by ID."""
    inc = incident_repository.get_incident(db, id)
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {id} not found")
    return IncidentDetailResponse(
        id=inc.id,
        title=inc.title,
        service_name=inc.service_name,
        severity=inc.severity,
        status=inc.status,
        started_at=inc.started_at,
        created_at=inc.created_at,
    )


@router.get("/{id}/report", response_model=ReportResponse)
def get_incident_report(id: UUID, db: Session = Depends(get_db)) -> ReportResponse:
    """Fetch final investigation report for an incident."""
    report = incident_repository.get_report_for_incident(db, id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report for incident {id} not found or investigation still in progress",
        )
    return ReportResponse.model_validate(report)
