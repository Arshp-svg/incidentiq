"""Pydantic request and response schemas for REST API."""

from uuid import UUID
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["live", "ready", "degraded"]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: dict[str, Any] = Field(default_factory=dict)


class IncidentDetailResponse(BaseModel):
    id: UUID
    title: str
    service_name: str
    severity: str
    status: str
    started_at: datetime
    created_at: datetime


class IncidentListResponse(BaseModel):
    items: list[IncidentDetailResponse]
    total: int
    limit: int
    offset: int


class IncidentEventResponse(BaseModel):
    id: UUID
    incident_id: UUID
    source_event_id: str
    service_name: str
    event_type: str
    occurred_at: datetime
    payload: dict[str, Any]
    s3_key: str | None = None


class JobStatusResponse(BaseModel):
    job_id: UUID
    incident_id: UUID
    status: Literal["queued", "running", "completed", "failed"]
    attempt_count: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class RootCauseResponse(BaseModel):
    claim: str
    confidence: float
    evidence_ids: list[str]


class ReportResponse(BaseModel):
    incident_id: str
    summary: str
    root_cause: RootCauseResponse
    affected_services: list[str]
    alternatives: list[str] = Field(default_factory=list)
    recommended_checks: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class DemoRunResponse(BaseModel):
    incident_id: UUID
    job_id: UUID
    status: str = "queued"
    status_url: str


class EventItem(BaseModel):
    event_id: str
    timestamp: datetime
    service: str
    event_type: str
    severity: Literal["low", "medium", "high", "critical"]
    message: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class IncidentCreateRequest(BaseModel):
    title: str
    service_name: str
    severity: Literal["low", "medium", "high", "critical"]
    events: list[EventItem] = Field(default_factory=list)


class FeedbackCreateRequest(BaseModel):
    rating: Literal["helpful", "incorrect", "incomplete"]
    comment: str | None = None


class FeedbackResponse(BaseModel):
    id: UUID
    incident_id: UUID
    rating: str
    comment: str | None = None
    created_at: datetime
