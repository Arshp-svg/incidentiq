"""Unit tests for event schemas, report schemas, and deterministic evidence validators."""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from incidentiq.events.schemas import TelemetryEvent, IncidentNotification
from incidentiq.agents.output import IncidentReport, RootCauseHypothesis, validate_report_evidence


def test_telemetry_event_schema_valid():
    """Verify standard telemetry event parsing."""
    event = TelemetryEvent(
        event_id="evt-unit-1",
        timestamp=datetime.now(timezone.utc),
        service="checkout",
        event_type="error",
        severity="high",
        message="Database query timeout",
        attributes={"query_time_ms": 3200},
    )
    assert event.event_id == "evt-unit-1"
    assert event.service == "checkout"
    assert event.severity == "high"
    assert event.attributes["query_time_ms"] == 3200


def test_telemetry_event_severity_validation():
    """Verify invalid severity values are rejected by schema."""
    with pytest.raises(ValidationError):
        TelemetryEvent(
            event_id="evt-bad",
            timestamp=datetime.now(timezone.utc),
            service="checkout",
            event_type="error",
            severity="catastrophic",  # Invalid severity value
            message="Test",
        )


def test_incident_report_schema_valid():
    """Verify structured IncidentReport Pydantic schema."""
    report = IncidentReport(
        incident_id="inc-test-01",
        summary="Service failure due to database degradation",
        root_cause=RootCauseHypothesis(
            claim="Database latency spike in orders-db",
            confidence=0.85,
            evidence_ids=["evt-001", "evt-002"],
        ),
        affected_services=["checkout", "orders"],
        alternatives=["Recent deployment introduced unindexed query"],
        recommended_checks=["Inspect active database connection count"],
        limitations=["Database connection metrics were not attached"],
    )
    assert report.incident_id == "inc-test-01"
    assert report.root_cause.confidence == 0.85
    assert len(report.root_cause.evidence_ids) == 2


def test_deterministic_evidence_validator_accepts_valid_evidence():
    """Verify validator accepts report when all cited IDs resolve to telemetry."""
    events = [
        {"event_id": "evt-001", "service": "checkout", "message": "error 1"},
        {"event_id": "evt-002", "service": "orders", "message": "error 2"},
    ]
    report_dict = {
        "incident_id": "inc-val-01",
        "summary": "Valid test summary",
        "root_cause": {
            "claim": "Valid claim",
            "confidence": 0.8,
            "evidence_ids": ["evt-001", "evt-002"],
        },
        "affected_services": ["checkout"],
        "alternatives": [],
        "recommended_checks": [],
        "limitations": [],
    }
    is_valid, errors = validate_report_evidence(report_dict, events)
    assert is_valid is True
    assert len(errors) == 0


def test_deterministic_evidence_validator_rejects_hallucinated_ids():
    """Verify validator rejects report citing nonexistent evidence IDs."""
    events = [
        {"event_id": "evt-001", "service": "checkout", "message": "error 1"},
    ]
    report_dict = {
        "incident_id": "inc-val-02",
        "summary": "Hallucinated ID test",
        "root_cause": {
            "claim": "Claim with fake evidence",
            "confidence": 0.9,
            "evidence_ids": ["evt-001", "evt-fake-999"],  # evt-fake-999 does not exist
        },
        "affected_services": ["checkout"],
    }
    is_valid, errors = validate_report_evidence(report_dict, events)
    assert is_valid is False
    assert any("evt-fake-999" in err for err in errors)


def test_deterministic_evidence_validator_rejects_empty_affected_services():
    """Verify validator rejects reports without affected services."""
    events = [{"event_id": "evt-001"}]
    report_dict = {
        "incident_id": "inc-val-03",
        "summary": "Missing affected services",
        "root_cause": {
            "claim": "Claim",
            "confidence": 0.8,
            "evidence_ids": ["evt-001"],
        },
        "affected_services": [],  # Empty
    }
    is_valid, errors = validate_report_evidence(report_dict, events)
    assert is_valid is False
    assert any("affected_services" in err for err in errors)
