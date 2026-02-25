# 5.4.5 Evidence

Capture release-gate and rollback simulation evidence here.

## Recommended commands

```bash
mkdir -p infra/evidence/5.4.5

# Start full stage-like local stack with observability.
DEPLOY_ENV=staging docker compose -f infra/docker-compose.yml --profile observability up --build -d

# Run go/no-go release gates.
set -o pipefail
infra/scripts/release_gate_check.sh --api-url http://localhost:8000 --prom-url http://localhost:9090 \
  | tee "infra/evidence/5.4.5/staging-$(date +%Y%m%d-%H%M%S)-release-gates.log"

# Run promote+rollback simulation.
DEPLOY_ENV=staging infra/scripts/release_simulation.sh --api-url http://localhost:8000
```

Attach:
- Release gate output log
- Rollback simulation logs
- Dashboard/alert references used during verification

## Captured local evidence (2026-02-24)
- `dev-20260224-221908-release-gates.log` (pass)
- `staging-20260224-214238-01-baseline-pass.log` (pass)
- `staging-20260224-214238-02-bad-release.log` (expected fail)
- `staging-20260224-214238-03-rollback-pass.log` (pass)
