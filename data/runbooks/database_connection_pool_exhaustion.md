# Runbook: Database Connection Pool Exhaustion

## Service: orders
## Related Dependencies: orders-db

### Summary
Diagnosis and resolution guide when backend services fail to acquire connections from the PostgreSQL relational database pool.

### Symptoms
- Error messages stating: "Timeout: Pool exhausted, connection cannot be acquired within 5000ms" or "FATAL: remaining connection slots are reserved for non-replication superuser connections".
- High response latency and queuing across all endpoints querying `orders-db`.
- Database server CPU may appear low or normal while client services stall.

### Root Cause Hypotheses
1. Connection leak in application code (unclosed database sessions or unreleased connection context managers).
2. Sudden traffic surge exceeding configured `max_connections` or connection pool max_size.
3. Slow transactions blocking connection reuse in the pool.

### Investigation Steps
1. Query current active connection count by client address and state:
   `SELECT count(*), state, client_addr FROM pg_stat_activity GROUP BY state, client_addr;`
2. Inspect application thread dumps or worker metrics for stuck workers waiting on pool checkout.
3. Verify connection pool settings in application configuration (e.g. `pool_size`, `max_overflow`).

### Mitigation Steps
1. Restart degraded worker pods to immediately release orphaned client connections.
2. Adjust `pool_size` and `pool_timeout` settings if database server hardware has available capacity.
3. Deploy connection pooling proxy (such as PgBouncer) if application instance count is causing connection explosion.
