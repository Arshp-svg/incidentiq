"""Demo trigger endpoint for launching seeded incident scenarios."""

import json
from pathlib import Path
from fastapi import APIRouter, Depends, Header, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session

from services.api.dependencies import get_db
from incidentiq.db.repositories import incident_repository
from services.worker.runner import run_investigation_job
from services.api.schemas.reports import DemoRunResponse

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

# Idempotency store for demo triggers
_DEMO_IDEMPOTENCY: dict[str, dict] = {}


@router.post("/run", response_model=DemoRunResponse, status_code=status.HTTP_202_ACCEPTED)
def run_demo_incident(
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> DemoRunResponse:
    """Trigger the seeded checkout-service outage demo scenario.
    
    Returns 202 Accepted immediately with the job ID and status URL.
    The investigation workflow executes asynchronously in the background.
    """
    # 1. Idempotency Check
    if idempotency_key:
        if idempotency_key in _DEMO_IDEMPOTENCY:
            return DemoRunResponse.model_validate(_DEMO_IDEMPOTENCY[idempotency_key])

    # 2. Load the seeded scenario
    scenario_path = Path(__file__).resolve().parents[3] / "data" / "scenarios" / "checkout_latency.json"
    if not scenario_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Demo scenario file data/scenarios/checkout_latency.json not found",
        )

    with open(scenario_path, "r", encoding="utf-8") as f:
        scenario = json.load(f)

    # 3. Create Incident, Job, and Events in PostgreSQL and upload raw events to MinIO
    inc, job = incident_repository.create_incident_with_events(
        db=db,
        title=scenario["title"],
        service_name=scenario["service_name"],
        severity=scenario["severity"],
        events_data=scenario.get("events", []),
        idempotency_key=idempotency_key,
    )

    # 4. Schedule investigation in background
    background_tasks.add_task(run_investigation_job, str(inc.id), str(job.id))

    response = DemoRunResponse(
        incident_id=inc.id,
        job_id=job.id,
        status="queued",
        status_url=f"/api/v1/jobs/{job.id}",
    )

    if idempotency_key:
        _DEMO_IDEMPOTENCY[idempotency_key] = response.model_dump(mode="json")

    return response
