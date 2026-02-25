# Deployment Health Gating Policy

## Scope
This policy standardizes liveness/readiness behavior for all deployment targets:
- local (`docker compose`)
- dev
- staging
- prod

## Endpoint contract
- Liveness: `GET /health/live`
  - Expected: HTTP `200`
  - Purpose: process is up
- Readiness: `GET /health/ready`
  - Expected: HTTP `200` only when dependencies are ready
  - Purpose: safe to receive traffic

Any non-`200` readiness response is a deployment gate failure.

## Probe policy by target
- local (`docker compose`)
  - `api` healthcheck must call `/health/ready`.
  - `web` must depend on healthy `api`.
  - `db` must be healthy before `api` starts.
- dev/staging/prod
  - Platform-level readiness probe must target `/health/ready`.
  - Platform-level liveness probe must target `/health/live`.
  - Traffic cutover/promotion is blocked until readiness is `200`.
  - Release must fail if readiness remains degraded through gate timeout.

## Deploy-time smoke gate
Use:

```bash
infra/scripts/deploy_health_gate.sh --api-url "$API_URL" --timeout-seconds 180 --interval-seconds 2
```

Pass criteria:
- both `/health/live` and `/health/ready` return `200` within timeout.

Fail criteria:
- timeout, connection failure, or any non-`200` readiness at timeout.

## Evidence requirements (for 5.4.1 closeout)
- Save gate output log under: `infra/evidence/5.4.1/`.
- Record:
  - target env (`dev|staging|prod`)
  - API URL
  - command used
  - timestamp
  - pass/fail result
