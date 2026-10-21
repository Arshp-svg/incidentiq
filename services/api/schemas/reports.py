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
