#!/usr/bin/env bash
set -euo pipefail

PROM_URL="${PROM_URL:-http://localhost:9090}"
API_URL="${API_URL:-http://localhost:8000}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-120}"
HEALTH_INTERVAL_SECONDS="${HEALTH_INTERVAL_SECONDS:-2}"
SKIP_PROMETHEUS="false"

usage() {
  cat <<'USAGE'
Usage: infra/scripts/release_gate_check.sh [options]

Release go/no-go gates:
  1) Deploy health gate passes (/health/live + /health/ready both 200)
  2) Error rate gate:   error_rate <= 5% over 5m (/api/chat + /upload)
  3) Chat p95 gate:     p95 latency <= 3s over 5m (/api/chat)
  4) Readiness gate:    readiness 503 increase over 2m == 0

Options:
  --prom-url URL                 Prometheus base URL (default: http://localhost:9090)
  --api-url URL                  API base URL for deploy health gate (default: http://localhost:8000)
  --health-timeout-seconds N     Deploy health gate timeout (default: 120)
  --health-interval-seconds N    Deploy health gate poll interval (default: 2)
  --skip-prometheus              Only run deploy health gate
  -h, --help                     Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prom-url)
      PROM_URL="$2"
      shift 2
      ;;
    --api-url)
      API_URL="$2"
      shift 2
      ;;
    --health-timeout-seconds)
      HEALTH_TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --health-interval-seconds)
      HEALTH_INTERVAL_SECONDS="$2"
      shift 2
      ;;
    --skip-prometheus)
      SKIP_PROMETHEUS="true"
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

for cmd in curl python3; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Missing required command: ${cmd}" >&2
    exit 2
  fi
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

"${ROOT_DIR}/infra/scripts/deploy_health_gate.sh" \
  --api-url "${API_URL}" \
  --timeout-seconds "${HEALTH_TIMEOUT_SECONDS}" \
  --interval-seconds "${HEALTH_INTERVAL_SECONDS}"

if [[ "${SKIP_PROMETHEUS}" == "true" ]]; then
  echo "Release gates passed (health only; prometheus skipped)"
  exit 0
fi

prom_query() {
  local query="$1"
  local resp
  local value

  resp="$(curl -fsS -G "${PROM_URL%/}/api/v1/query" --data-urlencode "query=${query}")"
  value="$(printf '%s' "${resp}" | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d.get("data",{}).get("result",[]); print(r[0]["value"][1] if r else "0")')"
  printf '%s' "${value}"
}

check_gate() {
  local name="$1"
  local value="$2"
  local threshold="$3"
  local op="$4"

  python3 - "$name" "$value" "$threshold" "$op" <<'PY'
import sys
name, value_s, threshold_s, op = sys.argv[1:5]
value = float(value_s)
threshold = float(threshold_s)
if op == "le":
    ok = value <= threshold
    relation = "<="
elif op == "eq":
    ok = value == threshold
    relation = "=="
else:
    raise SystemExit(f"unsupported op: {op}")

print(f"gate={name} value={value:.6f} target={relation}{threshold:.6f}")
if not ok:
    raise SystemExit(1)
PY
}

ERROR_RATE_EXPR='(
  sum(rate(atlas_http_requests_total{route=~"/api/chat|/upload",status=~"5.."}[5m]))
  /
  clamp_min(sum(rate(atlas_http_requests_total{route=~"/api/chat|/upload"}[5m])), 0.001)
)'
CHAT_P95_EXPR='histogram_quantile(0.95, sum(rate(atlas_http_request_latency_seconds_bucket{route="/api/chat"}[5m])) by (le))'
READINESS_EXPR='increase(atlas_http_requests_total{route="/health/ready",status="503"}[2m])'

error_rate="$(prom_query "${ERROR_RATE_EXPR}")"
chat_p95="$(prom_query "${CHAT_P95_EXPR}")"
readiness_failures="$(prom_query "${READINESS_EXPR}")"

check_gate "error_rate" "${error_rate}" "0.05" "le"
check_gate "chat_p95_seconds" "${chat_p95}" "3.0" "le"
check_gate "readiness_503_increase_2m" "${readiness_failures}" "0.0" "eq"

echo "Release gates passed"
