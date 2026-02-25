# Runbook: LLM/Embeddings Provider Outage (5.4.3)

## Symptoms
- `/api/chat` returns SSE `error` events with dependency/provider failure details.
- `/health/ready` may degrade to `503` when embeddings provider checks fail.
- Prometheus alerts may show rising `atlas_provider_errors_total` and elevated API error rate.

## Triage
1. Confirm readiness/liveness:
   - `curl -sS -i http://localhost:8000/health/live`
   - `curl -sS -i http://localhost:8000/health/ready`
2. Check provider-related logs:
   - `DEPLOY_ENV=<env> docker compose -f infra/docker-compose.yml logs --no-color --tail=300 api`
3. Identify active provider config:
   - `DEPLOY_ENV=<env> docker compose -f infra/docker-compose.yml exec api env | rg '^(LLM_PROVIDER|EMBEDDINGS_PROVIDER|OLLAMA_BASE_URL|OPENAI_BASE_URL)='`

## Mitigation
1. LLM outage fallback:
   - Switch to an available provider in `infra/env/<env>.llm.env`.
   - Recreate API: `DEPLOY_ENV=<env> docker compose -f infra/docker-compose.yml up -d --build api`
2. Embeddings outage fallback:
   - For emergency recovery, switch `EMBEDDINGS_PROVIDER=hash` in `infra/env/<env>.api.env`.
   - Recreate API as above.
3. Re-run deploy health gate:
   - `infra/scripts/deploy_health_gate.sh --api-url <api-url> --timeout-seconds 180 --interval-seconds 2`

## Recovery checks
- Readiness stable at `200` for at least 2 minutes.
- `infra/scripts/release_gate_check.sh --api-url <api-url> --prom-url <prom-url>` passes.
- Error-rate and provider-error metrics return to baseline.
