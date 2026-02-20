# Observability Stack (OSS)

This folder contains a local OSS observability stack for Milestone 5.2.

## Services
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001` (`admin` / `admin`)

## Start
```bash
cd infra/observability
docker compose up -d
```

## Notes
- Prometheus scrapes the API at `host.docker.internal:8000/metrics`.
- Ensure the API is running locally on port `8000` before validating dashboards.
- Grafana provisions:
  - Prometheus datasource
  - `Atlas API Overview` dashboard
