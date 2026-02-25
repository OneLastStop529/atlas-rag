# Release Gates (5.4.4)

Stage promotion to production is blocked unless all gates pass.

## Gate thresholds
- Error rate gate: `/api/chat` + `/upload` 5xx rate over 5m must be `<= 5%`.
- Chat latency gate: `/api/chat` p95 over 5m must be `<= 3s`.
- Readiness gate: `/health/ready` 503 increase over 2m must be `== 0`.
- Deploy health gate: `/health/live` and `/health/ready` must both return `200` within timeout.

These thresholds are aligned with Prometheus alerts in `infra/observability/prometheus/alerts.yml`.

## Go/No-Go command

```bash
infra/scripts/release_gate_check.sh --api-url <api-url> --prom-url <prom-url>
```

Behavior:
- Exits `0` only when deploy health gate and all metric thresholds pass.
- Exits non-zero on any gate breach and should block promotion.

## Stage before prod
Run gates in staging first. Promote to prod only after stage gates pass.
