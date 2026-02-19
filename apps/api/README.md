# API Runtime Notes

## Reliability Controls
- `PG_CONNECT_TIMEOUT_SECONDS` (default: `5`): Postgres connect timeout.
- `PG_STATEMENT_TIMEOUT_MS` (default: `15000`): Postgres statement timeout for retrieval/upload DB calls.
- `DEPENDENCY_RETRY_ATTEMPTS` (default: `2`): Max attempts for retryable dependency calls.
- `DEPENDENCY_RETRY_BASE_SECONDS` (default: `0.2`): Base retry backoff delay.
- `DEPENDENCY_RETRY_MAX_SECONDS` (default: `2.0`): Max retry backoff delay.
- `DEPENDENCY_TIMEOUT_SECONDS` (default: `30`): Soft timeout budget for embeddings operations.
- `EMBEDDINGS_HTTP_TIMEOUT_SECONDS` (default: `30`): TEI HTTP timeout.
- `READINESS_CACHE_TTL_SECONDS` (default: `5`): Cache TTL for readiness response.

## Health Endpoints
- `GET /health` and `GET /health/live`: liveness.
- `GET /health/ready`: dependency readiness (DB, pgvector, embeddings provider). Returns `503` when degraded.
