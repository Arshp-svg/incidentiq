"""FastAPI main application entry point for IncidentIQ."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.api.routes.health import router as health_router
from services.api.routes.incidents import router as incidents_router
from services.api.routes.jobs import router as jobs_router

app = FastAPI(
    title="IncidentIQ API",
    description="Evidence-Grounded AI Incident Investigation Platform API",
    version="0.1.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(health_router)
app.include_router(incidents_router)
app.include_router(jobs_router)


@app.get("/")
def root():
    return {
        "service": "IncidentIQ API",
        "docs_url": "/docs",
        "health_live": "/health/live",
        "health_ready": "/health/ready",
    }
