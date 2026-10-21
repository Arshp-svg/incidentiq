"""Generator script to build the 40-case labeled synthetic evaluation dataset for IncidentIQ.

Covers Scenarios A through E:
- Scenario A: Database latency spike
- Scenario B: Faulty deployment
- Scenario C: External payment provider outage
- Scenario D: Connection-pool exhaustion
- Scenario E: Unrelated errors with insufficient evidence (abstention cases)
"""

import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "evaluation"
OUTPUT_FILE = DATA_DIR / "incidents.json"


def generate_evaluation_dataset() -> list[dict]:
    incidents = []

    # -------------------------------------------------------------
    # Scenario A: Database Latency Spike (8 cases)
    # -------------------------------------------------------------
    scenario_a_configs = [
        ("checkout", "orders-db", "orders", "SELECT * FROM orders WHERE status = 'pending'", 3800),
        ("orders", "orders-db", "orders", "UPDATE orders SET status = 'processing'", 4200),
        ("inventory", "inventory-db", "inventory", "SELECT stock_count FROM items WHERE sku = 'SKU-882'", 3500),
        ("billing", "billing-db", "invoices", "SELECT * FROM invoices WHERE paid = false", 4900),
        ("checkout", "catalog-db", "products", "SELECT * FROM products WHERE category = 'featured'", 3100),
        ("orders", "orders-db", "order_items", "INSERT INTO order_items (order_id, item_id) VALUES ($1, $2)", 4100),
        ("cart", "cart-db", "active_carts", "SELECT cart_items FROM carts WHERE user_id = $1", 3600),
        ("checkout", "orders-db", "transactions", "SELECT * FROM transactions WHERE status = 'authorized'", 4500),
    ]

    for idx, (svc, db, tbl, query, latency) in enumerate(scenario_a_configs, start=1):
        inc_id = f"eval-a-{idx:02d}"
        e1 = f"evt-{inc_id}-1"
        e2 = f"evt-{inc_id}-2"
        e3 = f"evt-{inc_id}-3"
        e4 = f"evt-{inc_id}-4"
        incidents.append({
            "id": inc_id,
            "scenario_type": "A",
            "title": f"{svc.capitalize()} latency surge caused by slow {db} queries on {tbl}",
            "service_name": svc,
            "severity": "high",
            "ground_truth": {
                "known_cause": "Database latency spike",
                "expected_claim_keywords": ["database", "latency", "query"],
                "expected_runbook": "checkout_database_latency.md",
                "expected_evidence_ids": [e1, e2],
                "should_abstain": False,
            },
            "events": [
                {
                    "event_id": e1,
                    "timestamp": f"2026-10-20T14:{idx:02d}:00Z",
                    "service": svc,
                    "event_type": "error",
                    "severity": "high",
                    "message": f"Database request to {db} timed out after {latency}ms",
                    "attributes": {"database": db, "duration_ms": latency, "timeout_limit_ms": 3000},
                },
                {
                    "event_id": e2,
                    "timestamp": f"2026-10-20T14:{idx:02d}:15Z",
                    "service": db,
                    "event_type": "error",
                    "severity": "high",
                    "message": f"Slow query execution detected on table {tbl} ({latency}ms)",
                    "attributes": {"database": db, "query": query, "duration_ms": latency},
                },
                {
                    "event_id": e3,
                    "timestamp": f"2026-10-20T14:{idx:02d}:30Z",
                    "service": "api-gateway",
                    "event_type": "warning",
                    "severity": "medium",
                    "message": f"Upstream response time elevated for /{svc}",
                    "attributes": {"upstream": svc, "duration_ms": latency + 200},
                },
                {
                    "event_id": e4,
                    "timestamp": f"2026-10-20T14:{idx:02d}:45Z",
                    "service": "telemetry-collector",
                    "event_type": "info",
                    "severity": "low",
                    "message": "Routine scrape metrics successfully exported",
                    "attributes": {"batch_size": 128},
                },
            ],
        })

    # -------------------------------------------------------------
    # Scenario B: Faulty Deployment (8 cases)
    # -------------------------------------------------------------
    scenario_b_configs = [
        ("orders", "v2.4.0", "v2.3.9", "NullPointerException in OrderDiscountCalculator.java:45"),
        ("checkout", "v1.8.2", "v1.8.1", "TypeError: Cannot read properties of undefined (reading 'taxRate')"),
        ("auth", "v3.1.0", "v3.0.4", "AttributeError: 'NoneType' object has no attribute 'public_key'"),
        ("payments", "v2.0.5", "v2.0.4", "ClassCastException: PaymentMethodPayload cannot be cast to TokenizedCard"),
        ("inventory", "v1.5.0", "v1.4.8", "KeyError: 'warehouse_id' missing in inventory payload parser"),
        ("frontend-api", "v4.2.1", "v4.2.0", "ReferenceError: processEnvOverride is not defined in server bundle"),
        ("shipping", "v1.2.3", "v1.2.2", "AssertionError: Carrier rate lookup requires non-empty zip_code"),
        ("checkout", "v1.9.0", "v1.8.9", "UnhandledException: Missing currency converter configuration"),
    ]

    for idx, (svc, bad_ver, old_ver, err_msg) in enumerate(scenario_b_configs, start=1):
        inc_id = f"eval-b-{idx:02d}"
        e1 = f"evt-{inc_id}-1"
        e2 = f"evt-{inc_id}-2"
        e3 = f"evt-{inc_id}-3"
        e4 = f"evt-{inc_id}-4"
        incidents.append({
            "id": inc_id,
            "scenario_type": "B",
            "title": f"Application crash loop and 500 spike after deployment {bad_ver} of {svc}",
            "service_name": svc,
            "severity": "critical",
            "ground_truth": {
                "known_cause": "Faulty deployment",
                "expected_claim_keywords": ["deployment", "version", "release", "rollback"],
                "expected_runbook": "deployment_rollback_procedure.md",
                "expected_evidence_ids": [e1, e2],
                "should_abstain": False,
            },
            "events": [
                {
                    "event_id": e1,
                    "timestamp": f"2026-10-20T15:{idx:02d}:00Z",
                    "service": svc,
                    "event_type": "deployment",
                    "severity": "medium",
                    "message": f"Deployment roll-out completed for {svc} version {bad_ver} (replaced {old_ver})",
                    "attributes": {"deployment_version": bad_ver, "previous_version": old_ver, "status": "deployed"},
                },
                {
                    "event_id": e2,
                    "timestamp": f"2026-10-20T15:{idx:02d}:15Z",
                    "service": svc,
                    "event_type": "error",
                    "severity": "critical",
                    "message": f"Fatal unhandled exception in request handler: {err_msg}",
                    "attributes": {"deployment_version": bad_ver, "error": err_msg, "exit_code": 1},
                },
                {
                    "event_id": e3,
                    "timestamp": f"2026-10-20T15:{idx:02d}:30Z",
                    "service": "api-gateway",
                    "event_type": "error",
                    "severity": "high",
                    "message": f"HTTP 500 Internal Server Error surge from upstream {svc}",
                    "attributes": {"upstream": svc, "status_code": 500, "error_count": 480},
                },
                {
                    "event_id": e4,
                    "timestamp": f"2026-10-20T15:{idx:02d}:45Z",
                    "service": "cdn",
                    "event_type": "info",
                    "severity": "low",
                    "message": "Edge cache revalidation sweep completed",
                    "attributes": {"purged_keys": 14},
                },
            ],
        })

    # -------------------------------------------------------------
    # Scenario C: External Payment Provider Outage (8 cases)
    # -------------------------------------------------------------
    scenario_c_configs = [
        ("payments", "api.stripe.com", 503, "Payment gateway returned HTTP 503 Service Unavailable"),
        ("checkout", "secure-gateway.adyen.com", 504, "Upstream payment provider gateway timeout"),
        ("payments", "api.paypal.com", 502, "Bad Gateway from external merchant provider"),
        ("subscriptions", "api.braintreegateway.com", 500, "Recurring charge execution failed at remote provider"),
        ("payments", "api.stripe.com", 504, "Connection timed out contacting Stripe charge endpoint"),
        ("checkout", "api.adyen.com", 503, "Payment processing service unavailable upstream"),
        ("billing", "api.stripe.com", 502, "Stripe webhooks and charge APIs unreachable"),
        ("payments", "api.checkout.com", 504, "Card tokenization request timed out at merchant gateway"),
    ]

    for idx, (svc, provider_host, code, err_msg) in enumerate(scenario_c_configs, start=1):
        inc_id = f"eval-c-{idx:02d}"
        e1 = f"evt-{inc_id}-1"
        e2 = f"evt-{inc_id}-2"
        e3 = f"evt-{inc_id}-3"
        e4 = f"evt-{inc_id}-4"
        incidents.append({
            "id": inc_id,
            "scenario_type": "C",
            "title": f"Payment processing failures due to third-party outage at {provider_host}",
            "service_name": svc,
            "severity": "high",
            "ground_truth": {
                "known_cause": "External payment provider outage",
                "expected_claim_keywords": ["payment", "provider", "gateway", "external"],
                "expected_runbook": "payment_gateway_outage.md",
                "expected_evidence_ids": [e1, e2],
                "should_abstain": False,
            },
            "events": [
                {
                    "event_id": e1,
                    "timestamp": f"2026-10-20T16:{idx:02d}:00Z",
                    "service": svc,
                    "event_type": "error",
                    "severity": "high",
                    "message": f"External API request to {provider_host} failed with HTTP {code}: {err_msg}",
                    "attributes": {"provider_host": provider_host, "http_status": code, "duration_ms": 5000},
                },
                {
                    "event_id": e2,
                    "timestamp": f"2026-10-20T16:{idx:02d}:15Z",
                    "service": svc,
                    "event_type": "warning",
                    "severity": "medium",
                    "message": f"Circuit breaker OPEN for external provider {provider_host}",
                    "attributes": {"provider": provider_host, "failure_rate": 0.85},
                },
                {
                    "event_id": e3,
                    "timestamp": f"2026-10-20T16:{idx:02d}:30Z",
                    "service": "checkout",
                    "event_type": "error",
                    "severity": "high",
                    "message": "Customer checkout failed: Payment authorization declined due to upstream provider error",
                    "attributes": {"error_code": "PAYMENT_GATEWAY_ERROR"},
                },
                {
                    "event_id": e4,
                    "timestamp": f"2026-10-20T16:{idx:02d}:45Z",
                    "service": "notification",
                    "event_type": "info",
                    "severity": "low",
                    "message": "Customer SMS delivery dispatched",
                    "attributes": {"sms_status": "sent"},
                },
            ],
        })

    # -------------------------------------------------------------
    # Scenario D: Connection-Pool Exhaustion (8 cases)
    # -------------------------------------------------------------
    scenario_d_configs = [
        ("orders", "orders-db", 100, 100, "Timeout acquiring connection from pool after 10000ms"),
        ("checkout", "orders-db", 50, 50, "Connection pool exhausted: 50/50 connections leased"),
        ("inventory", "inventory-db", 40, 40, "No free connections available in HikariPool-1"),
        ("analytics", "analytics-db", 30, 30, "Database connection pool reached max size 30 with 45 callers waiting"),
        ("orders", "orders-db", 100, 100, "SQLAlchemy PoolTimeout: QueuePool size 100 overflow 20 reached"),
        ("cart", "cart-db", 60, 60, "Connection pool saturation: active=60, pending_waiters=25"),
        ("billing", "billing-db", 50, 50, "Pool limit reached for billing-db; worker threads blocking on acquire"),
        ("checkout", "orders-db", 100, 100, "HikariCP: Connection is not available, request timed out after 30000ms"),
    ]

    for idx, (svc, db, max_c, act_c, err_msg) in enumerate(scenario_d_configs, start=1):
        inc_id = f"eval-d-{idx:02d}"
        e1 = f"evt-{inc_id}-1"
        e2 = f"evt-{inc_id}-2"
        e3 = f"evt-{inc_id}-3"
        e4 = f"evt-{inc_id}-4"
        incidents.append({
            "id": inc_id,
            "scenario_type": "D",
            "title": f"Database connection pool exhaustion on {db} impacting {svc}",
            "service_name": svc,
            "severity": "high",
            "ground_truth": {
                "known_cause": "Connection-pool exhaustion",
                "expected_claim_keywords": ["connection", "pool", "exhaustion", "saturation"],
                "expected_runbook": "database_connection_pool_exhaustion.md",
                "expected_evidence_ids": [e1, e2],
                "should_abstain": False,
            },
            "events": [
                {
                    "event_id": e1,
                    "timestamp": f"2026-10-20T17:{idx:02d}:00Z",
                    "service": svc,
                    "event_type": "error",
                    "severity": "high",
                    "message": f"Connection acquisition timeout on {db}: {err_msg}",
                    "attributes": {"database": db, "active_connections": act_c, "max_connections": max_c},
                },
                {
                    "event_id": e2,
                    "timestamp": f"2026-10-20T17:{idx:02d}:15Z",
                    "service": svc,
                    "event_type": "warning",
                    "severity": "medium",
                    "message": f"Connection pool usage at 100% capacity ({act_c}/{max_c})",
                    "attributes": {"database": db, "utilization_percent": 100.0},
                },
                {
                    "event_id": e3,
                    "timestamp": f"2026-10-20T17:{idx:02d}:30Z",
                    "service": svc,
                    "event_type": "error",
                    "severity": "high",
                    "message": "Incoming HTTP request rejected: 503 Service Unavailable (database pool exhausted)",
                    "attributes": {"status_code": 503},
                },
                {
                    "event_id": e4,
                    "timestamp": f"2026-10-20T17:{idx:02d}:45Z",
                    "service": "session-manager",
                    "event_type": "info",
                    "severity": "low",
                    "message": "Periodic expired session cleanup completed",
                    "attributes": {"deleted_sessions": 3},
                },
            ],
        })

    # -------------------------------------------------------------
    # Scenario E: Unrelated Errors with Insufficient Evidence (8 cases - Abstention)
    # -------------------------------------------------------------
    scenario_e_configs = [
        ("checkout", "Cache miss on non-critical promotional banner asset", "Static banner fallback rendered"),
        ("orders", "Minor formatting warning in log output formatting", "Log serializer dropped unexpected null field"),
        ("inventory", "Background telemetry reporter queue flush deferred", "Flush rescheduled in 10s"),
        ("notifications", "Single transient unsubscribe token invalid format", "Client submitted empty token string"),
        ("auth", "User typed incorrect password (failed login attempt)", "Standard authentication refusal returned"),
        ("billing", "PDF receipt generator completed in 1.2s instead of 0.8s", "Non-blocking latency variation"),
        ("frontend-api", "Client terminated connection before HTTP 200 payload completed", "Client closed TCP socket"),
        ("cart", "Promotional coupon code 'EXPIRED2025' rejected as expired", "Expected coupon validation error"),
    ]

    for idx, (svc, msg1, msg2) in enumerate(scenario_e_configs, start=1):
        inc_id = f"eval-e-{idx:02d}"
        e1 = f"evt-{inc_id}-1"
        e2 = f"evt-{inc_id}-2"
        incidents.append({
            "id": inc_id,
            "scenario_type": "E",
            "title": f"Sporadic uncorroborated alerts on {svc} with insufficient telemetry evidence",
            "service_name": svc,
            "severity": "low",
            "ground_truth": {
                "known_cause": "Unrelated errors with insufficient evidence",
                "expected_claim_keywords": ["inconclusive", "insufficient", "unrelated", "uncertain"],
                "expected_runbook": None,
                "expected_evidence_ids": [],
                "should_abstain": True,
            },
            "events": [
                {
                    "event_id": e1,
                    "timestamp": f"2026-10-20T18:{idx:02d}:00Z",
                    "service": svc,
                    "event_type": "info",
                    "severity": "low",
                    "message": msg1,
                    "attributes": {"diagnostic": "benign"},
                },
                {
                    "event_id": e2,
                    "timestamp": f"2026-10-20T18:{idx:02d}:30Z",
                    "service": svc,
                    "event_type": "warning",
                    "severity": "low",
                    "message": msg2,
                    "attributes": {"handled": True},
                },
            ],
        })

    return incidents


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    incidents = generate_evaluation_dataset()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(incidents, f, indent=2)

    print(f"Successfully generated {len(incidents)} labeled incidents at:")
    print(f"  {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
