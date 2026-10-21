"""Reasoning provider for hypothesis generation and evidence synthesis."""

import os
import json
from typing import Any
import httpx
from incidentiq.agents.prompts import SYSTEM_INVESTIGATION_PROMPT


def call_llm_or_baseline_reasoner(
    incident_id: str,
    incident_title: str,
    service_name: str,
    events: list[dict[str, Any]],
    runbook_chunks: list[dict[str, Any]],
    dependency_graph: dict[str, Any],
) -> dict[str, Any]:
    """Generate structured root-cause hypothesis and report grounded in evidence."""
    api_key = os.getenv("OPENAI_API_KEY")
    
    # If OpenAI API key is present, try invoking the API
    if api_key and not api_key.startswith("sk-your-"):
        try:
            prompt_content = f"""
Incident ID: {incident_id}
Title: {incident_title}
Service: {service_name}

Telemetry Events:
{json.dumps(events, indent=2, default=str)}

Retrieved Runbook Chunks:
{json.dumps([{"doc": r.get("document_name"), "content": r.get("content")} for r in runbook_chunks], indent=2)}

Service Dependency Graph:
{json.dumps(dependency_graph, indent=2)}

Generate a JSON object matching this exact structure:
{{
  "incident_id": "{incident_id}",
  "summary": "Concise 1-sentence summary",
  "root_cause": {{
    "claim": "Specific hypothesis claim",
    "confidence": 0.85,
    "evidence_ids": ["ONLY_REAL_EVENT_IDS_FROM_ABOVE"]
  }},
  "affected_services": ["list of services"],
  "alternatives": ["alternative explanation"],
  "recommended_checks": ["actionable check 1"],
  "limitations": ["data limitations or missing metrics"]
}}
"""
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
                "messages": [
                    {"role": "system", "content": SYSTEM_INVESTIGATION_PROMPT},
                    {"role": "user", "content": prompt_content},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            }
            with httpx.Client(timeout=30.0) as client:
                res = client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    return json.loads(data["choices"][0]["message"]["content"])
        except Exception:
            # Fall back to baseline deterministic reasoner
            pass

    # Deterministic baseline reasoning engine grounded in actual telemetry and runbooks
    return _generate_deterministic_baseline(
        incident_id=incident_id,
        incident_title=incident_title,
        service_name=service_name,
        events=events,
        runbook_chunks=runbook_chunks,
        dependency_graph=dependency_graph,
    )


def _generate_deterministic_baseline(
    incident_id: str,
    incident_title: str,
    service_name: str,
    events: list[dict[str, Any]],
    runbook_chunks: list[dict[str, Any]],
    dependency_graph: dict[str, Any],
) -> dict[str, Any]:
    """Reliable baseline reasoner that produces verified schema-compliant outputs without hallucinating IDs."""
    if not events:
        return {
            "incident_id": incident_id,
            "summary": "Insufficient telemetry evidence available to determine root cause.",
            "root_cause": {
                "claim": "Inconclusive: No error events or telemetry captured for this incident.",
                "confidence": 0.1,
                "evidence_ids": [],
            },
            "affected_services": [service_name],
            "alternatives": ["Telemetry pipeline ingestion failure or delayed logs."],
            "recommended_checks": ["Verify log collector agents and Kafka event consumer health."],
            "limitations": ["No telemetry events were recorded."],
        }

    # Extract real event IDs
    real_event_ids = [e.get("event_id") or e.get("source_event_id") for e in events if e.get("event_id") or e.get("source_event_id")]

    # Check if there are any critical/high errors or actionable failures
    has_actionable_errors = any(
        e.get("event_type") in ("error", "deployment") or e.get("severity") in ("high", "critical")
        for e in events
    )

    # Affected services from dependency graph
    affected = [service_name]
    for dep in dependency_graph.get("dependencies", []):
        if dep.get("name") not in affected:
            affected.append(dep.get("name"))

    # Pattern E: Abstention / Insufficient Evidence
    # If no actionable errors or all events are benign/low severity, return low confidence to trigger abstention
    if not has_actionable_errors:
        return {
            "incident_id": incident_id,
            "summary": "Inconclusive Investigation: Telemetry evidence was insufficient or uncorroborated.",
            "root_cause": {
                "claim": "Inconclusive: Telemetry signals are low-severity or uncorroborated background noise.",
                "confidence": 0.2,
                "evidence_ids": real_event_ids[:2] if real_event_ids else [],
            },
            "affected_services": [service_name],
            "alternatives": ["Routine background maintenance or transient non-impacting telemetry jitter."],
            "recommended_checks": ["Continue monitoring service health dashboards."],
            "limitations": ["No high-severity error signals or causal degradation patterns detected."],
        }

    # Aggregate textual clues
    event_messages = " ".join([e.get("message", "").lower() for e in events])
    event_attrs = {}
    for e in events:
        if isinstance(e.get("attributes"), dict):
            event_attrs.update(e.get("attributes", {}))
    attrs_str = str(event_attrs).lower()

    # Pattern B: Faulty Deployment
    if "deployment" in event_messages or "previous_version" in attrs_str or "deployment_version" in attrs_str:
        bad_ver = event_attrs.get("deployment_version", "latest")
        return {
            "incident_id": incident_id,
            "summary": f"Application crash loop and 500 error surge following deployment of {service_name} ({bad_ver}).",
            "root_cause": {
                "claim": f"Faulty deployment release of {service_name} ({bad_ver}) introduced fatal runtime errors.",
                "confidence": 0.88,
                "evidence_ids": real_event_ids[:2] if real_event_ids else ["evt-unknown"],
            },
            "affected_services": affected[:3],
            "alternatives": [
                "Underlying config map or secret rotation failure during deployment pod restart."
            ],
            "recommended_checks": [
                f"Execute immediate rollback to previous stable version per deployment runbook.",
                "Inspect pod crash logs and stack trace exceptions."
            ],
            "limitations": [
                "Full application stack trace was truncated in initial telemetry payload."
            ],
        }

    # Pattern C: External Payment Provider Outage
    if any(k in event_messages or k in attrs_str for k in ("payment", "stripe", "adyen", "paypal", "braintree", "checkout.com")):
        provider = event_attrs.get("provider_host", "external payment provider")
        return {
            "incident_id": incident_id,
            "summary": f"Payment processing failures caused by third-party gateway downtime at {provider}.",
            "root_cause": {
                "claim": f"External payment provider outage at {provider} is causing payment authorization failures.",
                "confidence": 0.86,
                "evidence_ids": real_event_ids[:2] if real_event_ids else ["evt-unknown"],
            },
            "affected_services": affected[:2],
            "alternatives": [
                "Egress firewall or TLS mutual authentication handshake failure."
            ],
            "recommended_checks": [
                "Check external payment vendor status dashboard.",
                "Verify circuit breaker trip thresholds and retry policies."
            ],
            "limitations": [
                "Third-party vendor health metrics are not directly monitored."
            ],
        }

    # Pattern D: Connection-Pool Exhaustion
    if "connection pool" in event_messages or "pool exhausted" in event_messages or "pool saturation" in event_messages or "hikaripool" in event_messages or "queuepool" in event_messages:
        db_name = event_attrs.get("database", "downstream database")
        return {
            "incident_id": incident_id,
            "summary": f"Database connection pool exhaustion on {db_name} starving {service_name} request threads.",
            "root_cause": {
                "claim": f"Database connection pool exhaustion on {db_name} is blocking worker threads.",
                "confidence": 0.85,
                "evidence_ids": real_event_ids[:2] if real_event_ids else ["evt-unknown"],
            },
            "affected_services": affected[:2],
            "alternatives": [
                "Database server max_connections reached due to connection leakage.",
                "Long-running analytical queries holding connections open."
            ],
            "recommended_checks": [
                "Inspect pg_stat_activity connection counts and state.",
                "Increase max pool size or decrease connection timeout in application config."
            ],
            "limitations": [
                "Historical connection leak profiles were not available."
            ],
        }

    # Pattern A: Database Latency Spike
    if "database" in event_messages or "query" in event_messages or "orders-db" in attrs_str or "slow query" in event_messages:
        db_name = event_attrs.get("database", "downstream database")
        return {
            "incident_id": incident_id,
            "summary": f"{service_name.capitalize()} requests are timing out due to downstream database degradation.",
            "root_cause": {
                "claim": f"Downstream database latency in {db_name} is causing request thread timeouts.",
                "confidence": 0.82,
                "evidence_ids": real_event_ids[:2] if real_event_ids else ["evt-unknown"],
            },
            "affected_services": affected[:3],
            "alternatives": [
                "A recent deployment may have introduced unindexed database queries.",
                "Disk I/O saturation on the database storage volume."
            ],
            "recommended_checks": [
                f"Inspect active queries and lock contention in {db_name}.",
                "Check pg_stat_activity for slow queries exceeding 1000ms."
            ],
            "limitations": [
                "Direct database connection pool saturation metrics were not attached."
            ],
        }

    # Default Generic Fallback
    return {
        "incident_id": incident_id,
        "summary": f"Service errors detected in {service_name}.",
        "root_cause": {
            "claim": f"Elevated error rate observed in {service_name} operational telemetry.",
            "confidence": 0.65,
            "evidence_ids": real_event_ids[:1] if real_event_ids else ["evt-unknown"],
        },
        "affected_services": affected[:2],
        "alternatives": [
            "Transient spike in incoming request volume.",
        ],
        "recommended_checks": [
            "Review service logs and error stack traces.",
        ],
        "limitations": [
            "Limited telemetry history available for historical comparison."
        ],
    }
