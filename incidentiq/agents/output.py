"""Pydantic schemas and deterministic validators for investigation reports."""

from typing import Any
from pydantic import BaseModel, Field, field_validator


class RootCauseHypothesis(BaseModel):
    claim: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(min_length=1)


class IncidentReport(BaseModel):
    """Structured report schema specified on Page 7 of the blueprint."""
    incident_id: str
    summary: str
    root_cause: RootCauseHypothesis
    affected_services: list[str]
    alternatives: list[str] = Field(default_factory=list)
    recommended_checks: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def validate_report_evidence(
    report_dict: dict[str, Any],
    valid_events: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """Validate report structure and ensure cited evidence IDs exist in collected telemetry.
    
    Returns (is_valid, error_messages).
    """
    errors: list[str] = []
    
    # 1. Pydantic schema validation
    try:
        report = IncidentReport.model_validate(report_dict)
    except Exception as e:
        return False, [f"Schema validation error: {e}"]

    # 2. Strict evidence ID validation: every cited ID must exist in collected events
    valid_event_ids = {e.get("event_id") or e.get("source_event_id") for e in valid_events}
    for cited_id in report.root_cause.evidence_ids:
        if cited_id not in valid_event_ids:
            errors.append(f"Invalid evidence reference: '{cited_id}' was cited but does not exist in collected telemetry.")

    # 3. Affected services check
    if not report.affected_services:
        errors.append("Validation error: 'affected_services' cannot be empty.")

    is_valid = len(errors) == 0
    return is_valid, errors
