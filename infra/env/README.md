# Deployment Environment Files

`infra/docker-compose.yml` selects env files using `DEPLOY_ENV`:

- `dev`: `dev.db.env`, `dev.api.env`, `dev.llm.env`, `dev.web.env`
- `staging`: `staging.db.env`, `staging.api.env`, `staging.llm.env`, `staging.web.env`
- `prod`: `prod.db.env`, `prod.api.env`, `prod.llm.env`, `prod.web.env`

Embedding dimension defaults:
- `dev`: `PGVECTOR_DIM=384`, `HASH_EMBEDDING_DIM=384`, `EXPECTED_EMBEDDING_DIM=384`
- `staging`: `PGVECTOR_DIM=768`, `HASH_EMBEDDING_DIM=768`, `EXPECTED_EMBEDDING_DIM=768`
- `prod`: `PGVECTOR_DIM=1024`, `HASH_EMBEDDING_DIM=1024`, `EXPECTED_EMBEDDING_DIM=1024`

Examples:

```bash
DEPLOY_ENV=dev docker compose -f infra/docker-compose.yml up -d
DEPLOY_ENV=staging docker compose -f infra/docker-compose.yml up -d
DEPLOY_ENV=prod docker compose -f infra/docker-compose.yml up -d
```

Keep secrets out of git for real staging/prod deployments.

Canonical startup/deploy matrix + required secrets:
- `infra/deployment/STARTUP_ENV_MATRIX.md`

Vector schema is auto-initialized only on first DB volume initialization (`rag_pgdata`).  
Manual re-apply (idempotent) is available per env:

```bash
DEPLOY_ENV=dev bash infra/scripts/init_schema.sh
DEPLOY_ENV=staging bash infra/scripts/init_schema.sh
DEPLOY_ENV=prod bash infra/scripts/init_schema.sh
```

Switch an environment to OpenAI:

```bash
# Example for staging: edit infra/env/staging.llm.env
LLM_PROVIDER=openai
OPENAI_API_KEY=replace_with_real_key
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
```
