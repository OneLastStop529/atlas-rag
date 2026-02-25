# Runbook: Ingestion Backlog / Queue Pressure (5.4.3)

## Symptoms
- Upload latency rises and user uploads time out.
- Chunk/file ingestion throughput flattens while request volume grows.
- API remains live but user-visible ingest progress stalls.

## Triage
1. Check upload and API latency panels in Grafana (`atlas-api-overview`).
2. Check API logs for slow ingest stages (`upload_ingest`) and DB timeout signals.
3. Verify DB health and resource pressure:
   - `DEPLOY_ENV=<env> docker compose -f infra/docker-compose.yml logs --no-color --tail=300 api db`

## Mitigation
1. Throttle ingestion traffic temporarily (operational policy):
   - Reduce concurrent upload clients or pause bulk ingest jobs.
2. Prioritize interactive chat traffic by scheduling ingest during off-peak windows.
3. If DB is saturated, restore DB performance first using vector DB runbook actions.
4. If provider calls dominate ingest time, apply provider outage fallback.

## Drain strategy
1. Keep service healthy and avoid full downtime if `/health/ready` is stable.
2. Process backlog in bounded batches, then re-check p95 latency and error rate.
3. Resume normal ingest concurrency only after release gates pass.

## Recovery checks
- Upload latency trend returns near baseline.
- Error-rate gate remains under threshold.
- `infra/scripts/release_gate_check.sh --api-url <api-url> --prom-url <prom-url>` passes.
