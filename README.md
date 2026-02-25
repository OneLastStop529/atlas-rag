# atlas-rag
Atlas(RAG) is a production-oriented Retrieval Augmented Generation (RAG) platform for chatting with your documents using streaming responses and source citations. Under the hood it pairs a FastAPI backend with pgvector-powered similarity search and a Next.js frontend for uploads, search, and chat-style Q&A, giving you a clear local-to-prod path for document ingestion and retrieval.

## Milestone plan
- Project milestone tracking and closeout checklist: `RAG_MILESTONE_PLAN.md`

## Local setup (frontend + backend + database)
This repo is split into:
- `apps/web`: Next.js frontend
- `apps/api`: FastAPI backend
- `infra`: Postgres + pgvector Docker compose and schema

## Dockerized stack (db + api + web)
Use `infra/docker-compose.yml` to run core services with health-gated startup.

```bash
DEPLOY_ENV=dev docker compose -f infra/docker-compose.yml up --build -d
```

Deployment env var segregation:
- `DEPLOY_ENV=dev|staging|prod` selects service env files under `infra/env/`.
- Loaded files:
  - `infra/env/<DEPLOY_ENV>.db.env`
  - `infra/env/<DEPLOY_ENV>.api.env`
  - `infra/env/<DEPLOY_ENV>.llm.env`
  - `infra/env/<DEPLOY_ENV>.web.env`
- Default when unset: `dev`.
- For web build-time API URL, set `NEXT_PUBLIC_API_URL` in shell when building non-dev images.
  Example: `DEPLOY_ENV=staging NEXT_PUBLIC_API_URL=https://api.staging.example.com docker compose -f infra/docker-compose.yml up --build -d`

LLM provider segregation:
- LLM provider and model/base URL are configured per env in `infra/env/<DEPLOY_ENV>.llm.env`.
- To use OpenAI in an env, set `LLM_PROVIDER=openai` and provide `OPENAI_API_KEY` in that env file.
- Canonical startup/deploy env + required-secrets matrix: `infra/deployment/STARTUP_ENV_MATRIX.md`.

Schema initialization:

```bash
DEPLOY_ENV=dev docker compose -f infra/docker-compose.yml up --build -d
```

- Schema init runs via Postgres `docker-entrypoint-initdb.d` on first volume initialization and applies `infra/schema.template.sql` with the selected `PGVECTOR_DIM`.
- Manual re-run is still available when needed:
  `DEPLOY_ENV=dev bash infra/scripts/init_schema.sh`

Service URLs:
- Web: `http://localhost:3000`
- API: `http://localhost:8000`
- API readiness: `http://localhost:8000/health/ready`

Enable observability profile (Prometheus + Grafana):

```bash
DEPLOY_ENV=dev docker compose -f infra/docker-compose.yml --profile observability up -d
```

Observability URLs:
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001` (`admin` / `admin`)

Notes:
- Compose sets `EMBEDDINGS_PROVIDER=hash` for lightweight local startup.
- `LLM_PROVIDER=ollama` is configured by default and expects Ollama on host `11434`.
- Browser-side API URL is baked at web build time via `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

Stop services:

```bash
DEPLOY_ENV=dev docker compose -f infra/docker-compose.yml down
```

### Deployment health gate (5.4.1)
Probe policy is documented in:
- `infra/deployment/HEALTH_GATING_POLICY.md`

Deploy-time smoke gate command (fails release on degraded readiness):

```bash
infra/scripts/deploy_health_gate.sh --api-url http://localhost:8000 --timeout-seconds 120 --interval-seconds 2
```

Evidence logging example:

```bash
set -o pipefail
infra/scripts/deploy_health_gate.sh --api-url http://localhost:8000 --timeout-seconds 120 --interval-seconds 2 \
  | tee "infra/evidence/5.4.1/dev-$(date +%Y%m%d-%H%M%S)-health-gate.log"
```

### 1) Start the database (Postgres + pgvector)
The docker compose file uses `pgvector/pgvector:pg16` with default credentials.

```bash
DEPLOY_ENV=dev docker compose -f infra/docker-compose.yml up -d
```

Schema is initialized automatically only when `rag_pgdata` is first created (fresh DB volume).  
If you need to re-apply it manually (idempotent):

```bash
DEPLOY_ENV=dev bash infra/scripts/init_schema.sh
```

Default connection string:

```
postgresql://rag:rag@localhost:5432/rag
```

### 2) Run the backend (FastAPI)
The backend reads `DATABASE_URL` and defaults to a local embeddings provider.

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Create an `.env` file (or export env vars) in your shell:

```
DATABASE_URL=postgresql://rag:rag@localhost:5432/rag
# Optional: embeddings provider (defaults to "hf_local")
# EMBEDDINGS_PROVIDER=hf_local
# HF_EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

### LLM provider configuration
The chat endpoint streams responses from a configurable LLM provider.

```
# Choose provider: "ollama" (default) or "openai" (case-insensitive)
LLM_PROVIDER=ollama

# Optional: timeout (seconds) for all LLM calls
LLM_TIMEOUT_S=60

# Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# OpenAI (hosted)
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
# Optional: custom OpenAI-compatible base URL
OPENAI_BASE_URL=https://api.openai.com/v1

# Optional: override the system prompt. Supports {context} and {query}.
# Example: "Use only the context.\nCONTEXT:\n{context}\nQUESTION:\n{query}\n"
LLM_SYSTEM_PROMPT=You are a helpful assistant. Use only the provided context.\nCONTEXT:\n{context}\n
```

LLM test endpoint:
```
POST /api/llm/test
body: { "provider": "ollama|openai", "model": "...", "base_url": "..." }
```

### Advanced retrieval rollout flags (Milestone 5.3)
`/api/chat` supports advanced retrieval rollout + sampled shadow eval via env vars:

```
ADV_RETRIEVAL_ENABLED=false
ADV_RETRIEVAL_ALLOW_REQUEST_OVERRIDE=false
RETRIEVAL_STRATEGY=baseline               # baseline|advanced_hybrid|advanced_hybrid_rerank
RERANKER_VARIANT=rrf_simple               # rrf_simple|cross_encoder
QUERY_REWRITE_POLICY=disabled             # disabled|simple|llm
ADV_RETRIEVAL_ROLLOUT_PERCENT=0           # 0-100
ADV_RETRIEVAL_EVAL_MODE=off               # off|shadow
ADV_RETRIEVAL_EVAL_SAMPLE_PERCENT=0       # 0-100
ADV_RETRIEVAL_EVAL_TIMEOUT_MS=2000        # 250-30000
```

Recommended defaults by environment:
- `dev`: `ADV_RETRIEVAL_ENABLED=true`, `RETRIEVAL_STRATEGY=advanced_hybrid`, `ADV_RETRIEVAL_ROLLOUT_PERCENT=100`, `ADV_RETRIEVAL_EVAL_MODE=shadow`, `ADV_RETRIEVAL_EVAL_SAMPLE_PERCENT=100`
- `staging`: same as `dev`
- `prod`: `ADV_RETRIEVAL_ENABLED=true`, `RETRIEVAL_STRATEGY=advanced_hybrid`, `ADV_RETRIEVAL_ROLLOUT_PERCENT=0`, `ADV_RETRIEVAL_EVAL_MODE=shadow`, `ADV_RETRIEVAL_EVAL_SAMPLE_PERCENT=5`

Promotion gates (before increasing prod rollout):
- quality: top-1 source agreement rate >= `0.70` and jaccard median >= `0.50`
- latency: shadow-primary p95 delta <= `+500ms`
- reliability: no sustained error-rate regression (> `1%` absolute increase) during eval window

### 3) Run the frontend (Next.js)
The frontend expects the API base URL via `NEXT_PUBLIC_API_URL` and defaults to
`http://localhost:8000` if unset.

```bash
cd apps/web
npm install
npm run dev
```

If you want to set it explicitly, create `apps/web/.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 4) Quick sanity check
- API health: `GET http://localhost:8000/health`
- Web app: `http://localhost:3000`
- Stream chat (SSE):

```bash
curl -N http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"What documents are loaded?"}]}'
```

Expected SSE events: `token`, `citations`, `done` (and `error` on failure).

### SSE contract
Endpoint: `POST /api/chat` (content-type `application/json`, response `text/event-stream`)

Event types:
```
event: token
data: {"delta":"..."}

event: citations
data: {"items":[{"chunk_id":"...","document_id":"...","source":"...","page":1,"chunk_index":0,"distance":0.12,"snippet":"...","metadata":{}}]}

event: error
data: {"message":"..."}

event: done
data: {"ok":true}
```

### Upload contract
Upload API and UI request/response contract is defined in:

- `docs/INGEST_UPLOAD_CONTRACT.md`

### Troubleshooting
- If embeddings fail, ensure your DB vector dimension matches the embeddings model
  (schema is rendered from `infra/schema.template.sql` using `PGVECTOR_DIM` in `infra/env/<DEPLOY_ENV>.db.env`).
