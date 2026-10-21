"""State definition for the IncidentIQ investigation workflow."""

from typing import Any, TypedDict


class InvestigationState(TypedDict, total=False):
    """Workflow state as defined on Page 8 of the IncidentIQ blueprint."""
    incident_id: str
    job_id: str
    incident_title: str
    service_name: str
    severity: str
    events: list[dict[str, Any]]
    runbook_chunks: list[dict[str, Any]]
    dependency_graph: dict[str, Any]
    hypotheses: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    report: dict[str, Any]
    errors: list[str]
    retry_count: int
    evidence_sufficient: bool
