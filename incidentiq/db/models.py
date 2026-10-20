"""SQLAlchemy declarative models for IncidentIQ PostgreSQL tables."""

import uuid
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from incidentiq.db.session import Base


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=False)
    service_name = Column(Text, nullable=False)
    severity = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default="open")
    started_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name="chk_incidents_severity"),
        CheckConstraint("status IN ('open', 'investigating', 'resolved')", name="chk_incidents_status"),
    )


class InvestigationJob(Base):
    __tablename__ = "investigation_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    status = Column(Text, nullable=False, server_default="queued")
    attempt_count = Column(Integer, nullable=False, server_default="0")
    checkpoint_id = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'completed', 'failed')", name="chk_jobs_status"),
        Index("idx_jobs_status_created", "status", "created_at"),
    )


class IncidentEvent(Base):
    __tablename__ = "incident_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    source_event_id = Column(Text, nullable=False)
    service_name = Column(Text, nullable=False)
    event_type = Column(Text, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    payload = Column(JSONB, nullable=False)
    s3_key = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("incident_id", "source_event_id", name="uq_incident_source_event"),
        Index("idx_events_incident_time", "incident_id", "occurred_at"),
    )


class RunbookChunk(Base):
    __tablename__ = "runbook_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_name = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    embedding = Column(Vector(384), nullable=True)

    __table_args__ = (
        UniqueConstraint("document_name", "chunk_index", name="uq_runbook_document_chunk"),
    )


class InvestigationFinding(Base):
    __tablename__ = "investigation_findings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("investigation_jobs.id"), nullable=False)
    finding_type = Column(Text, nullable=False)
    claim = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)
    evidence = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False)
    rating = Column(Text, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint("rating IN ('helpful', 'incorrect', 'incomplete')", name="chk_feedback_rating"),
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aggregate_id = Column(UUID(as_uuid=True), nullable=False)
    event_type = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    published_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_outbox_unpublished", "created_at", postgresql_where=text("published_at IS NULL")),
    )
