# Runbook: Checkout Service Database Latency and Timeout Triaging

## Service: checkout
## Related Dependencies: orders, orders-db

### Summary
This runbook guides engineers through triaging and mitigating high latency and request timeouts in the checkout service caused by downstream database performance degradation.

### Symptoms
- Increased 504 Gateway Timeout or 500 Internal Server Error responses on `/api/v1/checkout`.
- P99 checkout response time exceeds 2500ms.
- Downstream database `orders-db` reports rising query execution times (>1500ms) and high active connection counts.
- Elevated error logs in checkout stating: "Database request timed out".

### Root Cause Hypotheses
1. **Unindexed Query Spike**: A recent deployment or increased traffic triggered full-table scans on `orders` or `order_items`.
2. **Lock Contention**: Concurrent transaction deadlocks or row locks on customer accounts holding database worker threads.
3. **Connection Pool Saturation**: The service max connections limit has been reached, causing connection acquisition waits.

### Investigation Steps
1. Inspect the service dependency graph: verify whether the bottleneck is in `checkout` or downstream in `orders` / `orders-db`.
2. Review slow query logs in `orders-db` for queries exceeding 1000ms.
3. Check database CPU utilization, memory pressure, and active connection count.
4. Verify if a new deployment was released within the past 60 minutes.

### Mitigation Steps
1. Kill long-running blocking transactions if safe: `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'active' AND duration > interval '3 minutes';`
2. If triggered by a faulty release, trigger the deployment rollback procedure immediately.
3. Scale up read replicas or increase connection pool size temporarily if resource limits permit.
