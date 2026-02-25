# Runbook: Vector DB Degradation/Outage (5.4.3)

## Symptoms
- `/health/ready` returns `503` with DB-related dependency failures.
- Upload and retrieval endpoints fail with DB timeout/connection errors.
- Increased latency and 5xx responses on `/api/chat` and `/upload`.

## Triage
1. Validate DB container status:
   - `DEPLOY_ENV=<env> docker compose -f infra/docker-compose.yml ps db api`
2. Check DB logs:
   - `DEPLOY_ENV=<env> docker compose -f infra/docker-compose.yml logs --no-color --tail=300 db`
3. Check extension/table readiness inside DB:
   - `DEPLOY_ENV=<env> docker compose -f infra/docker-compose.yml exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\dx'`
   - `DEPLOY_ENV=<env> docker compose -f infra/docker-compose.yml exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\dt'`

## Mitigation
1. Restart DB and API (local/single-node path):
   - `DEPLOY_ENV=<env> docker compose -f infra/docker-compose.yml restart db api`
2. If schema drift is suspected:
   - `DEPLOY_ENV=<env> bash infra/scripts/init_schema.sh`
3. Verify volume health/persistence before destructive actions.

## Recovery checks
- `curl -sS -i <api-url>/health/ready` returns `200`.
- `infra/scripts/deploy_health_gate.sh --api-url <api-url> --timeout-seconds 180 --interval-seconds 2` passes.
- `infra/scripts/release_gate_check.sh --api-url <api-url> --prom-url <prom-url>` passes.
