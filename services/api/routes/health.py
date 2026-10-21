"""Liveness and readiness health endpoints."""

from fastapi import APIRouter, Response, status
from sqlalchemy import text
from incidentiq.db.session import SessionLocal
from incidentiq.graph.client import get_driver
from incidentiq.storage.s3 import s3_service
from services.api.schemas.reports import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
def health_live() -> HealthResponse:
    """Liveness probe: verifies the API process is alive."""
    return HealthResponse(status="live", details={"api": "healthy"})


@router.get("/ready", response_model=HealthResponse)
def health_ready(response: Response) -> HealthResponse:
    """Readiness probe: honestly verifies database, graph, and object store connectivity."""
    details = {}
    is_ready = True

    # 1. Check PostgreSQL
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        details["postgres"] = "healthy"
    except Exception as e:
        details["postgres"] = f"unhealthy: {e}"
        is_ready = False

    # 2. Check Neo4j
    try:
        driver = get_driver()
        with driver.session() as session:
            session.run("RETURN 1")
        details["neo4j"] = "healthy"
    except Exception as e:
        details["neo4j"] = f"unhealthy: {e}"
        is_ready = False

    # 3. Check MinIO / S3
    try:
        s3_service.client.head_bucket(Bucket=s3_service.bucket_name)
        details["s3"] = "healthy"
    except Exception as e:
        details["s3"] = f"unhealthy: {e}"
        is_ready = False

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="degraded", details=details)

    return HealthResponse(status="ready", details=details)
