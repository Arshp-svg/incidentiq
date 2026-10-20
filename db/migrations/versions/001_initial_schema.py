"""Initial database schema for incidents, jobs, events, and outbox.

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-18 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Table: incidents
    op.create_table(
        'incidents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('service_name', sa.Text(), nullable=False),
        sa.Column('severity', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default='open'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("severity IN ('low', 'medium', 'high', 'critical')", name='chk_incidents_severity'),
        sa.CheckConstraint("status IN ('open', 'investigating', 'resolved')", name='chk_incidents_status'),
    )

    # 3. Table: investigation_jobs
    op.create_table(
        'investigation_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('incident_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('incidents.id'), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default='queued'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('checkpoint_id', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("status IN ('queued', 'running', 'completed', 'failed')", name='chk_jobs_status'),
    )
    op.create_index('idx_jobs_status_created', 'investigation_jobs', ['status', 'created_at'])

    # 4. Table: incident_events
    op.create_table(
        'incident_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('incident_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('incidents.id'), nullable=False),
        sa.Column('source_event_id', sa.Text(), nullable=False),
        sa.Column('service_name', sa.Text(), nullable=False),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('s3_key', sa.Text(), nullable=True),
        sa.UniqueConstraint('incident_id', 'source_event_id', name='uq_incident_source_event'),
    )
    op.create_index('idx_events_incident_time', 'incident_events', ['incident_id', 'occurred_at'])

    # 5. Table: runbook_chunks
    op.create_table(
        'runbook_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('document_name', sa.Text(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('embedding', Vector(384), nullable=True),
        sa.UniqueConstraint('document_name', 'chunk_index', name='uq_runbook_document_chunk'),
    )

    # 6. Table: investigation_findings
    op.create_table(
        'investigation_findings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('investigation_jobs.id'), nullable=False),
        sa.Column('finding_type', sa.Text(), nullable=False),
        sa.Column('claim', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('evidence', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # 7. Table: feedback
    op.create_table(
        'feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('incident_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('incidents.id'), nullable=False),
        sa.Column('rating', sa.Text(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("rating IN ('helpful', 'incorrect', 'incomplete')", name='chk_feedback_rating'),
    )

    # 8. Table: outbox_events
    op.create_table(
        'outbox_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('aggregate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        'idx_outbox_unpublished',
        'outbox_events',
        ['created_at'],
        postgresql_where=sa.text('published_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('idx_outbox_unpublished', table_name='outbox_events')
    op.drop_table('outbox_events')
    op.drop_table('feedback')
    op.drop_table('investigation_findings')
    op.drop_table('runbook_chunks')
    op.drop_index('idx_events_incident_time', table_name='incident_events')
    op.drop_table('incident_events')
    op.drop_index('idx_jobs_status_created', table_name='investigation_jobs')
    op.drop_table('investigation_jobs')
    op.drop_table('incidents')
