"""Verification script for Day 5 Task 1: Containerized Packaging & Production Configuration."""

import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from services.api.main import app
from incidentiq.config import settings


def verify_packaging():
    print("=" * 65)
    print(" Day 5 Task 1: Production Container Packaging Verification")
    print("=" * 65)

    # 1. Verify root Dockerfile
    dockerfile_backend = ROOT_DIR / "Dockerfile"
    print("\n[1/5] Checking Backend/Worker Dockerfile...", end=" ")
    assert dockerfile_backend.exists(), "Root Dockerfile does not exist!"
    content_be = dockerfile_backend.read_text(encoding="utf-8")
    assert "python:3.12-slim" in content_be
    assert "uvicorn" in content_be
    print("SUCCESS (Python 3.12 multi-purpose backend/worker image defined)")

    # 2. Verify frontend Dockerfile and Nginx configuration
    dockerfile_fe = ROOT_DIR / "apps" / "web" / "Dockerfile"
    nginx_conf = ROOT_DIR / "apps" / "web" / "nginx.conf"
    print("\n[2/5] Checking Frontend Multi-Stage Dockerfile & Nginx Conf...", end=" ")
    assert dockerfile_fe.exists(), "Frontend Dockerfile does not exist!"
    assert nginx_conf.exists(), "Frontend nginx.conf does not exist!"
    content_fe = dockerfile_fe.read_text(encoding="utf-8")
    assert "node:20-alpine" in content_fe
    assert "nginx:alpine" in content_fe
    content_ng = nginx_conf.read_text(encoding="utf-8")
    assert "proxy_pass http://api:8000" in content_ng
    assert "try_files $uri $uri/ /index.html" in content_ng
    print("SUCCESS (Vite build + Nginx reverse-proxy SPA routing defined)")

    # 3. Verify docker-compose.prod.yml
    compose_prod = ROOT_DIR / "docker-compose.prod.yml"
    print("\n[3/5] Checking Production Docker Compose Orchestration...", end=" ")
    assert compose_prod.exists(), "docker-compose.prod.yml does not exist!"
    content_comp = compose_prod.read_text(encoding="utf-8")
    for svc in ("postgres", "kafka", "neo4j", "minio", "api", "worker", "web"):
        assert f"{svc}:" in content_comp, f"Missing {svc} service in docker-compose.prod.yml"
    print("SUCCESS (Full 7-service containerized stack declared)")

    # 4. Verify CORS and allowed origins configuration
    print("\n[4/5] Checking Dynamic CORS and Allowed Origins...", end=" ")
    assert hasattr(settings, "CORS_ALLOWED_ORIGINS"), "CORS_ALLOWED_ORIGINS not in settings!"
    print(f"SUCCESS (Current configured origins: '{settings.CORS_ALLOWED_ORIGINS}')")

    # 5. Verify live API application and CORS headers
    print("\n[5/5] Testing API CORS Preflight & Health Probe...", end=" ")
    client = TestClient(app)
    res_health = client.get("/health/live")
    assert res_health.status_code == 200

    # Test OPTIONS preflight with Origin header
    res_cors = client.options(
        "/api/v1/incidents",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type,Idempotency-Key",
        },
    )
    assert res_cors.status_code in (200, 204), f"CORS preflight failed: {res_cors.status_code}"
    assert "access-control-allow-origin" in res_cors.headers
    print("SUCCESS (CORS preflight accepted with allowed origin)")

    print("\n" + "=" * 65)
    print(" ALL PRODUCTION PACKAGING CHECKS PASSED!")
    print("=" * 65)


if __name__ == "__main__":
    verify_packaging()
