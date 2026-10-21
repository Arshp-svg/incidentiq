# Multi-purpose Dockerfile for IncidentIQ API and Worker services
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (curl for healthcheck probes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy packaging configuration first to leverage Docker layer caching
COPY pyproject.toml README.md ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy application source code, migrations, and evaluation assets
COPY incidentiq ./incidentiq
COPY services ./services
COPY db ./db
COPY data ./data
COPY scripts ./scripts
COPY alembic.ini ./

EXPOSE 8000

# Default command runs the FastAPI application
CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
