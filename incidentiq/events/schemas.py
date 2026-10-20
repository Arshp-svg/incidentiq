"""Pydantic schemas for event contracts and Kafka messages."""

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class TelemetryEvent(BaseModel):
    """Event contract as specified in blueprint Page 6."""
    event_id: str = Field(default_factory=lambda: f"evt-{uuid4().hex[:8]}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service: str
    event_type: str
    severity: Literal["low", "medium", "high", "critical"]
    message: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class IncidentNotification(BaseModel):
    """Kafka payload carrying incident investigation trigger notifications."""
    incident_id: UUID = Field(default_factory=uuid4)
    job_id: UUID = Field(default_factory=uuid4)
    title: str
    service_name: str
    severity: Literal["low", "medium", "high", "critical"]
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    events: list[TelemetryEvent] = Field(default_factory=list)
