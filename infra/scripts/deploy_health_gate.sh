#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-120}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-2}"

usage() {
  cat <<'USAGE'
Usage: infra/scripts/deploy_health_gate.sh [options]

Options:
  --api-url URL            Base API URL (default: http://localhost:8000)
  --timeout-seconds N      Max wait time (default: 120)
  --interval-seconds N     Poll interval (default: 2)
  -h, --help               Show help

The gate passes only when both endpoints return HTTP 200:
  /health/live
  /health/ready
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-url)
      API_URL="$2"
      shift 2
      ;;
    --timeout-seconds)
      TIMEOUT_SECONDS="$2"
      shift 2
      ;;
    --interval-seconds)
      INTERVAL_SECONDS="$2"
      shift 2
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

for cmd in curl date; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "Missing required command: ${cmd}" >&2
    exit 2
  fi
done

if ! [[ "${TIMEOUT_SECONDS}" =~ ^[0-9]+$ ]] || ! [[ "${INTERVAL_SECONDS}" =~ ^[0-9]+$ ]]; then
  echo "timeout and interval must be non-negative integers" >&2
  exit 2
fi

health_code() {
  local path="$1"
  local url="${API_URL%/}${path}"
  local code
  if code="$(curl -sS -o /dev/null -w "%{http_code}" "${url}")"; then
    echo "${code}"
  else
    echo "000"
  fi
}

health_body() {
  local path="$1"
  local url="${API_URL%/}${path}"
  curl -sS "${url}" || true
}

start_ts="$(date +%s)"
attempt=0

echo "Health gate starting: api=${API_URL}, timeout=${TIMEOUT_SECONDS}s, interval=${INTERVAL_SECONDS}s"
while true; do
  attempt=$((attempt + 1))
  now_ts="$(date +%s)"
  elapsed=$((now_ts - start_ts))

  live_code="$(health_code "/health/live")"
  ready_code="$(health_code "/health/ready")"
  printf 'attempt=%d elapsed=%ss live=%s ready=%s\n' "${attempt}" "${elapsed}" "${live_code}" "${ready_code}"

  if [[ "${live_code}" == "200" && "${ready_code}" == "200" ]]; then
    echo "Health gate passed"
    exit 0
  fi

  if (( elapsed >= TIMEOUT_SECONDS )); then
    echo "Health gate failed: timeout waiting for live/ready to become 200" >&2
    echo "Last /health/live body: $(health_body "/health/live")" >&2
    echo "Last /health/ready body: $(health_body "/health/ready")" >&2
    exit 1
  fi

  sleep "${INTERVAL_SECONDS}"
done
