# Rollback Playbook (5.4.4)

## Preconditions
- Candidate release already deployed to stage.
- `infra/scripts/deploy_health_gate.sh` and `infra/scripts/release_gate_check.sh` are available.

## Deterministic rollback sequence
1. Identify deploy env (`staging` or `prod`) and API/Prometheus endpoints.
2. Re-apply last known-good compose config:
   - `DEPLOY_ENV=<env> docker compose -f infra/docker-compose.yml up -d --build api web`
3. Run readiness gate:
   - `infra/scripts/deploy_health_gate.sh --api-url <api-url> --timeout-seconds 180 --interval-seconds 2`
4. Run release go/no-go checks:
   - `infra/scripts/release_gate_check.sh --api-url <api-url> --prom-url <prom-url>`
5. Confirm alerts clear and no sustained readiness failures remain.

## Verified command-path simulation
Use the built-in simulation to verify release failure and rollback recovery:

```bash
DEPLOY_ENV=staging infra/scripts/release_simulation.sh --api-url http://localhost:8000
```

Expected:
- Baseline gate pass.
- Simulated bad release gate fail.
- Post-rollback gate pass.

Evidence logs are saved to `infra/evidence/5.4.5/`.
