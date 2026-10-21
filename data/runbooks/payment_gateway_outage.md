# Runbook: Third-Party Payment Gateway Outage

## Service: payments
## Related Dependencies: payment-gateway, checkout

### Summary
Procedures for identifying and managing failures in the `payments` service caused by third-party payment gateway downtime or network partition.

### Symptoms
- Sudden spike in payment authorization failures (HTTP 502/504).
- Error messages containing "Payment gateway connection reset" or "Provider timeout".
- Checkout completion rate drops sharply while product catalog browsing remains healthy.

### Root Cause Hypotheses
1. External payment vendor API degradation or global outage.
2. Expired TLS certificates or API authorization keys on outgoing provider webhooks.
3. Network egress routing partition between our infrastructure and external provider endpoints.

### Investigation Steps
1. Check the official public status page and API health status of the payment vendor.
2. Inspect `payments` service logs for egress HTTP status codes and response bodies.
3. Test connectivity to the provider endpoint from an egress container: `curl -ivs https://api.payment-gateway.example/health`.

### Mitigation Steps
1. If the primary provider is confirmed down, switch payment routing traffic to the secondary fallback payment processor.
2. Enable graceful degraded mode: inform customers during checkout that payment processing is undergoing maintenance rather than throwing hard 500 errors.
