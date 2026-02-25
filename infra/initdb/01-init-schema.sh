#!/bin/sh
set -eu

PGVECTOR_DIM="${PGVECTOR_DIM:-384}"
if ! echo "${PGVECTOR_DIM}" | grep -Eq '^[0-9]+$'; then
  echo "PGVECTOR_DIM must be numeric, got: ${PGVECTOR_DIM}" >&2
  exit 1
fi

POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-postgres}"

sed "s/__VECTOR_DIM__/${PGVECTOR_DIM}/g" /opt/bootstrap/schema.template.sql \
  | psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}"

echo "initdb: schema initialized with vector(${PGVECTOR_DIM})"
