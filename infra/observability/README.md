# Observability Stack (OSS)

This folder contains Prometheus/Grafana config used by the `observability` profile in `infra/docker-compose.yml`.

## Services
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001` (`admin` / `admin`)

## Start
```bash
DEPLOY_ENV=dev docker compose -f infra/docker-compose.yml --profile observability up -d
```

## Notes
- Prometheus scrapes the API at `api:8000/metrics` on the compose network.
- The observability profile starts alongside the API stack from the same compose file.
- Grafana provisions:
  - Prometheus datasource
  - `Atlas API Overview` dashboard
- Prometheus alert rules are loaded from `prometheus/alerts.yml`:
  - API error rate > 5% for 5m
  - Chat p95 latency > 3s for 10m
  - Readiness failures sustained for 2m
