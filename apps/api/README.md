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
- `EXPECTED_EMBEDDING_DIM` (optional): Fail readiness if provider embedding dim does not match this value.

## Health Endpoints
- `GET /health` and `GET /health/live`: liveness.
- `GET /health/ready`: dependency readiness (DB, pgvector, embeddings provider). Returns `503` when degraded.

## Advanced Retrieval Rollout (5.3)
### Flags
- `ADV_RETRIEVAL_ENABLED` (default: `false`)
- `ADV_RETRIEVAL_ALLOW_REQUEST_OVERRIDE` (default: `false`)
- `RETRIEVAL_STRATEGY` (default: `baseline`, allowed: `baseline|advanced_hybrid|advanced_hybrid_rerank`)
- `RERANKER_VARIANT` (default: `rrf_simple`, allowed: `rrf_simple|cross_encoder`)
- `QUERY_REWRITE_POLICY` (default: `disabled`, allowed: `disabled|simple|llm`)
- `ADV_RETRIEVAL_ROLLOUT_PERCENT` (default: `0`)
- `ADV_RETRIEVAL_EVAL_MODE` (default: `off`, allowed: `off|shadow`)
- `ADV_RETRIEVAL_EVAL_SAMPLE_PERCENT` (default: `0`)
- `ADV_RETRIEVAL_EVAL_TIMEOUT_MS` (default: `2000`)

### Environment defaults
- `dev`: rollout 100%, shadow eval 100%
- `staging`: rollout 100%, shadow eval 100%
- `prod`: rollout 0%, shadow eval 5%

### Promotion gates
- quality: top-1 agreement >= `0.70` and jaccard median >= `0.50`
- latency: shadow-primary p95 delta <= `+500ms`
- reliability: no sustained error-rate regression (> `1%` absolute)
