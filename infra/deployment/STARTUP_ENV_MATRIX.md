# Startup/Deploy Env Matrix (5.4.2)

## Deterministic startup sequence
API startup follows this order:
1. Parse and validate startup env config (`validate_startup_config`).
2. Run hard dependency checks (`database`, `pgvector`, `embeddings provider`).
3. Start serving traffic.

Implementation reference:
- `apps/api/app/main.py` (`lifespan`)
- `apps/api/app/core/startup_config.py`

## Env files by deployment target

`infra/docker-compose.yml` selects these files by `DEPLOY_ENV`:
- `dev`: `infra/env/dev.db.env`, `infra/env/dev.api.env`, `infra/env/dev.llm.env`, `infra/env/dev.web.env`
- `staging`: `infra/env/staging.db.env`, `infra/env/staging.api.env`, `infra/env/staging.llm.env`, `infra/env/staging.web.env`
- `prod`: `infra/env/prod.db.env`, `infra/env/prod.api.env`, `infra/env/prod.llm.env`, `infra/env/prod.web.env`

## Required startup variables (API)
- `DATABASE_URL` (required)
- `LLM_PROVIDER` in: `ollama|ollama_local|openai`
- `EMBEDDINGS_PROVIDER` in supported set (`hash`, `hf_local`, `tei`, `sentence-transformers`, `bge-small-zh`, `bge-large-zh`)

Provider-specific:
- when `LLM_PROVIDER=openai`: `OPENAI_BASE_URL` must be valid `http(s)` URL
- when `LLM_PROVIDER=ollama|ollama_local`: `OLLAMA_BASE_URL` must be valid `http(s)` URL

Dimension consistency:
- `EXPECTED_EMBEDDING_DIM` (if set) must be integer `> 0`
- `HASH_EMBEDDING_DIM` (if set) must be integer `> 0`
- if both are set, `HASH_EMBEDDING_DIM` must equal `EXPECTED_EMBEDDING_DIM`

## Required secrets by environment
- `dev`:
  - default (`LLM_PROVIDER=ollama`): no hosted LLM secret required
  - if using OpenAI: `OPENAI_API_KEY` required for runtime LLM calls
- `staging`:
  - if `LLM_PROVIDER=openai`: `OPENAI_API_KEY` required (inject via secret manager/CI)
- `prod`:
  - if `LLM_PROVIDER=openai`: `OPENAI_API_KEY` required (inject via secret manager/CI)

Notes:
- `OPENAI_API_KEY` is intentionally not a startup fail-fast requirement.
- Missing `OPENAI_API_KEY` with `LLM_PROVIDER=openai` is surfaced as a startup warning and fails at runtime call sites.
