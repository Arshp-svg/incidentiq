"""Unit tests for FastAPI endpoints, status codes, idempotency, and error handling."""

import uuid
from fastapi.testclient import TestClient
from services.api.main import app

client = TestClient(app)


def test_health_live_endpoint():
    """Verify GET /health/live returns 200 with process health."""
    res = client.get("/health/live")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "live"
    assert "timestamp" in data


def test_health_ready_endpoint():
    """Verify GET /health/ready reports dependency readiness truthfully."""
    res = client.get("/health/ready")
    assert res.status_code in (200, 503)
    data = res.json()
    assert "status" in data
    assert "details" in data
    assert "postgres" in data["details"]


def test_incident_creation_validation_error():
    """Verify POST /api/v1/incidents returns 422 for malformed payloads."""
    # Missing required 'service_name' and 'title'
    bad_payload = {"severity": "high"}
    res = client.post("/api/v1/incidents", json=bad_payload)
    assert res.status_code == 422


def test_idempotency_key_replay_and_conflict():
    """Verify Idempotency-Key caching returns identical incident on exact replay and 409 on conflict."""
    key = f"idem-unit-{uuid.uuid4()}"
    payload_a = {
        "title": "Unit Test Outage A",
        "service_name": "checkout",
        "severity": "high",
        "events": [],
    }
    headers = {"Idempotency-Key": key}

    # 1. First request -> 201 Created
    res1 = client.post("/api/v1/incidents", json=payload_a, headers=headers)
    assert res1.status_code == 201
    data1 = res1.json()
    incident_id_1 = data1["id"]

    # 2. Exact duplicate request with same key -> 201 with same incident id
    res2 = client.post("/api/v1/incidents", json=payload_a, headers=headers)
    assert res2.status_code == 201
    data2 = res2.json()
    assert data2["id"] == incident_id_1

    # 3. Same key with different payload -> 409 Conflict
    payload_b = {
        "title": "Mismatched Different Outage B",
        "service_name": "orders",
        "severity": "low",
        "events": [],
    }
    res3 = client.post("/api/v1/incidents", json=payload_b, headers=headers)
    assert res3.status_code == 409
    assert "Idempotency-Key" in res3.json()["detail"] or "Idempotency key" in res3.json()["detail"]


def test_incident_list_pagination():
    """Verify GET /api/v1/incidents returns valid paginated structure."""
    res = client.get("/api/v1/incidents?limit=3&offset=0")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert data["limit"] == 3
    assert data["offset"] == 0
    assert len(data["items"]) <= 3
