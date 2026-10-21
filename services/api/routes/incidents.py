"""Incident, Events, Feedback, and Ingestion API routes."""

import json
from uuid import UUID
from typing import Any
from fastapi import APIRouter, Depends, Header, HTTPException, Query, BackgroundTasks, status
from sqlalchemy.orm import Session

from services.api.dependencies import get_db
from incidentiq.db.repositories import incident_repository
from incidentiq.db.models import OutboxEvent
from services.worker.runner import run_investigation_job
from services.api.schemas.reports import (
    IncidentDetailResponse,
    IncidentListResponse,
    IncidentEventResponse,
    IncidentCreateRequest,
    FeedbackCreateRequest,
    FeedbackResponse,
    ReportResponse,
)

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])

# In-memory store for idempotency keys and original request hashes
_IDEMPOTENCY_STORE: dict[str, dict[str, Any]] = {}


@router.get("", response_model=IncidentListResponse)
def list_incidents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> IncidentListResponse:
    """List incidents with pagination."""
    items, total = incident_repository.list_incidents(db, limit=limit, offset=offset)
    return IncidentListResponse(
        items=[
            IncidentDetailResponse(
                id=inc.id,
                title=inc.title,
                service_name=inc.service_name,
                severity=inc.severity,
                status=inc.status,
                started_at=inc.started_at,
                created_at=inc.created_at,
            )
            for inc in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=IncidentDetailResponse, status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreateRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> IncidentDetailResponse:
    """Create an incident from an event batch and trigger investigation."""
    # 1. Handle idempotency
    payload_hash = json.dumps(payload.model_dump(mode="json"), sort_keys=True)
    if idempotency_key:
        if idempotency_key in _IDEMPOTENCY_STORE:
            cached = _IDEMPOTENCY_STORE[idempotency_key]
            if cached["hash"] != payload_hash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Incompatible reuse of Idempotency-Key: '{idempotency_key}'",
                )
            return IncidentDetailResponse.model_validate(cached["response"])

    # 2. Persist Incident and Events
    events_raw = [e.model_dump(mode="json") for e in payload.events]
    inc, job = incident_repository.create_incident_with_events(
        db=db,
        title=payload.title,
        service_name=payload.service_name,
        severity=payload.severity,
        events_data=events_raw,
        idempotency_key=idempotency_key,
    )

    # 3. Schedule investigation runner in background
    background_tasks.add_task(run_investigation_job, str(inc.id), str(job.id))

    response_data = IncidentDetailResponse(
        id=inc.id,
        title=inc.title,
        service_name=inc.service_name,
        severity=inc.severity,
        status=inc.status,
        started_at=inc.started_at,
        created_at=inc.created_at,
    )

    if idempotency_key:
        _IDEMPOTENCY_STORE[idempotency_key] = {
            "hash": payload_hash,
            "response": response_data.model_dump(mode="json"),
        }

    return response_data


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


@router.get("/{id}/events", response_model=list[IncidentEventResponse])
def get_incident_events(id: UUID, db: Session = Depends(get_db)) -> list[IncidentEventResponse]:
    """Fetch chronological events related to an incident."""
    inc = incident_repository.get_incident(db, id)
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {id} not found")

    events = incident_repository.get_incident_events(db, id)
    return [
        IncidentEventResponse(
            id=e.id,
            incident_id=e.incident_id,
            source_event_id=e.source_event_id,
            service_name=e.service_name,
            event_type=e.event_type,
            occurred_at=e.occurred_at,
            payload=e.payload if isinstance(e.payload, dict) else {},
            s3_key=e.s3_key,
        )
        for e in events
    ]


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


@router.post("/{id}/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def record_feedback(
    id: UUID,
    payload: FeedbackCreateRequest,
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """Record user feedback ('helpful', 'incorrect', 'incomplete') for an incident."""
    inc = incident_repository.get_incident(db, id)
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident {id} not found")

    inc.status = "resolved"
    db.commit()

    feedback = incident_repository.create_feedback(
        db=db,
        incident_id=id,
        rating=payload.rating,
        comment=payload.comment,
    )
    return FeedbackResponse(
        id=feedback.id,
        incident_id=feedback.incident_id,
        rating=feedback.rating,
        comment=feedback.comment,
        created_at=feedback.created_at,
    )
