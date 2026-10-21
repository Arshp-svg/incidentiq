# Runbook: Deployment Failure and Rollback Procedure

## Service: general / cross-service
## Related Dependencies: checkout, orders, payments

### Summary
Standard operating procedure for identifying regressions introduced by recent deployments and safely executing an automated or manual rollback.

### Symptoms
- Error rate increases sharply immediately following a CI/CD deployment timestamp (within 0–30 minutes).
- Canary or blue/green health checks fail.
- New uncaught exceptions or schema incompatibility errors appear in log traces.

### Root Cause Hypotheses
1. Code defect in new build artifact causing runtime NullPointer / AttributeError.
2. Incompatible database schema migration executed out-of-order with code deployment.
3. Missing environment variable or secret configuration in new release container spec.

### Investigation Steps
1. Identify the recent deployment version and release timestamp from service logs (`deployment_version`).
2. Compare git commit diff between previous stable version and current release.
3. Check error frequency vs baseline prior to the deployment timestamp.

### Mitigation Steps
1. Execute immediate service rollback to the previous stable release artifact version.
2. If a database migration accompanied the release, verify whether the schema is backward-compatible before rolling back containers.
3. Notify the on-call release coordinator and pause continuous deployment pipeline.
