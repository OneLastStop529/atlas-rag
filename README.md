# atlas-rag
Atlas(RAG) is a production-oriented Retrieval Augmented Generation (RAG) platform for chatting with your documents using streaming responses and source citations. Under the hood it pairs a FastAPI backend with pgvector-powered similarity search and a Next.js frontend for uploads, search, and chat-style Q&A, giving you a clear local-to-prod path for document ingestion and retrieval.

## Local setup (frontend + backend + database)
This repo is split into:
- `apps/web`: Next.js frontend
- `apps/api`: FastAPI backend
- `infra`: Postgres + pgvector Docker compose and schema

### 1) Start the database (Postgres + pgvector)
The docker compose file uses `pgvector/pgvector:pg16` with default credentials.

```bash
docker compose -f infra/docker-compose.yml up -d
```

Initialize the schema (tables + vector index) using the bundled SQL:

```bash
cat infra/schema.sql | docker compose -f infra/docker-compose.yml exec -T db psql -U rag -d rag
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

### Troubleshooting
- If embeddings fail, ensure your DB vector dimension matches the embeddings model
  (the default schema uses `vector(384)` in `infra/schema.sql`).
