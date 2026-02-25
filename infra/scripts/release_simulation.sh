#!/usr/bin/env bash
set -euo pipefail

DEPLOY_ENV="${DEPLOY_ENV:-staging}"
API_URL="${API_URL:-http://localhost:8000}"
KEEP_RUNNING="false"

usage() {
  cat <<'USAGE'
Usage: infra/scripts/release_simulation.sh [options]

Runs a local release simulation for 5.4.5:
  1) Baseline deploy gate pass (promote candidate)
  2) Simulated bad release (broken DATABASE_URL override) gate fails
  3) Rollback to baseline and gate passes again

Options:
  --deploy-env ENV         Env group to use (default: staging)
  --api-url URL            API URL for health gate (default: http://localhost:8000)
  --keep-running           Keep compose services up after run
  -h, --help               Show help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --deploy-env)
      DEPLOY_ENV="$2"
      shift 2
      ;;
    --api-url)
      API_URL="$2"
      shift 2
      ;;
    --keep-running)
      KEEP_RUNNING="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

for cmd in docker date tee; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Missing required command: ${cmd}" >&2
    exit 2
  fi
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BASE_COMPOSE=(docker compose -f "${ROOT_DIR}/infra/docker-compose.yml")
BAD_COMPOSE=(docker compose -f "${ROOT_DIR}/infra/docker-compose.yml" -f "${ROOT_DIR}/infra/deployment/overrides/bad-api.yml")
EVIDENCE_DIR="${ROOT_DIR}/infra/evidence/5.4.5"
TS="$(date +%Y%m%d-%H%M%S)"

mkdir -p "${EVIDENCE_DIR}"

cleanup() {
  if [[ "${KEEP_RUNNING}" == "false" ]]; then
    DEPLOY_ENV="${DEPLOY_ENV}" "${BASE_COMPOSE[@]}" down -v >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "[1/3] Starting baseline stack (db + api)"
DEPLOY_ENV="${DEPLOY_ENV}" "${BASE_COMPOSE[@]}" up --build -d db api

echo "[1/3] Baseline health gate (expect pass)"
set -o pipefail
"${ROOT_DIR}/infra/scripts/deploy_health_gate.sh" \
  --api-url "${API_URL}" \
  --timeout-seconds 180 \
  --interval-seconds 2 \
  | tee "${EVIDENCE_DIR}/${DEPLOY_ENV}-${TS}-01-baseline-pass.log"

echo "[2/3] Simulating bad release (broken DATABASE_URL override)"
DEPLOY_ENV="${DEPLOY_ENV}" "${BAD_COMPOSE[@]}" up --build -d api

echo "[2/3] Health gate during bad release (expect fail)"
if "${ROOT_DIR}/infra/scripts/deploy_health_gate.sh" \
  --api-url "${API_URL}" \
  --timeout-seconds 45 \
  --interval-seconds 2 \
  > "${EVIDENCE_DIR}/${DEPLOY_ENV}-${TS}-02-bad-release.log" 2>&1; then
  echo "Unexpected gate success during bad release" >&2
  exit 1
fi

echo "[3/3] Rolling back to baseline compose"
DEPLOY_ENV="${DEPLOY_ENV}" "${BASE_COMPOSE[@]}" up --build -d api

echo "[3/3] Post-rollback health gate (expect pass)"
"${ROOT_DIR}/infra/scripts/deploy_health_gate.sh" \
  --api-url "${API_URL}" \
  --timeout-seconds 180 \
  --interval-seconds 2 \
  | tee "${EVIDENCE_DIR}/${DEPLOY_ENV}-${TS}-03-rollback-pass.log"

echo "Release simulation passed"
echo "Evidence logs: ${EVIDENCE_DIR}/${DEPLOY_ENV}-${TS}-*.log"
