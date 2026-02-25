#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY_ENV="${DEPLOY_ENV:-dev}"
COMPOSE_FILE="${ROOT_DIR}/infra/docker-compose.yml"
DB_ENV_FILE="${ROOT_DIR}/infra/env/${DEPLOY_ENV}.db.env"
TEMPLATE_FILE="${ROOT_DIR}/infra/schema.template.sql"
PRINT_SQL_ONLY="${1:-}"

if [[ ! -f "${DB_ENV_FILE}" ]]; then
  echo "missing db env file: ${DB_ENV_FILE}" >&2
  exit 1
fi

if [[ ! -f "${TEMPLATE_FILE}" ]]; then
  echo "missing schema template: ${TEMPLATE_FILE}" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${DB_ENV_FILE}"
set +a

PGVECTOR_DIM="${PGVECTOR_DIM:-384}"
if ! [[ "${PGVECTOR_DIM}" =~ ^[0-9]+$ ]]; then
  echo "PGVECTOR_DIM must be a positive integer, got: ${PGVECTOR_DIM}" >&2
  exit 1
fi

: "${POSTGRES_USER:?POSTGRES_USER is required in ${DB_ENV_FILE}}"
: "${POSTGRES_DB:?POSTGRES_DB is required in ${DB_ENV_FILE}}"

echo "Initializing schema for DEPLOY_ENV=${DEPLOY_ENV} with vector(${PGVECTOR_DIM})"

if [[ "${PRINT_SQL_ONLY}" == "--print-sql" ]]; then
  sed "s/__VECTOR_DIM__/${PGVECTOR_DIM}/g" "${TEMPLATE_FILE}"
  exit 0
fi

sed "s/__VECTOR_DIM__/${PGVECTOR_DIM}/g" "${TEMPLATE_FILE}" | docker compose -f "${COMPOSE_FILE}" exec -T db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"

echo "Schema initialized successfully."
