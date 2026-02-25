# 5.4.1 Evidence

Store deployment health-gate logs here.

Example:

```bash
mkdir -p infra/evidence/5.4.1
DEPLOY_ENV=dev docker compose -f infra/docker-compose.yml up -d
set -o pipefail
infra/scripts/deploy_health_gate.sh --api-url http://localhost:8000 --timeout-seconds 120 --interval-seconds 2 \
  | tee "infra/evidence/5.4.1/dev-$(date +%Y%m%d-%H%M%S)-health-gate.log"
```

Promotion should use target API URL for `staging` and `prod`.
