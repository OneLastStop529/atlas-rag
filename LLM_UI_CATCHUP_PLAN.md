# Atlas RAG Catch-up Plan (LLM First, then UI/UX)

## Goals
- Replace the v0 deterministic synthesizer with real LLM streaming.
- Preserve existing retrieval + citations while improving answer quality.
- Bring the web UI to parity with rag_demo’s controls and usability.

## Milestone 0 — Baseline & Safety (prep)
- Confirm current chat endpoint contract and SSE events.
- Add basic error handling and timeouts around LLM calls.
- Document env vars for LLM provider selection in one place.

Deliverables
- Short README section describing LLM provider config and expected env vars.
- Minimal test plan: curl chat, see streamed tokens + citations + done.

## Milestone 1 — LLM Integration (core)
### 1.1: Wire LLM into `/chat`
- Replace `_v0_answer` in `apps/api/app/api/chat.py` with real LLM streaming.
- Use existing provider factory: `get_llm_provider()` from `apps/api/app/providers/factory.py`.
- Keep SSE event format (`token`, `citations`, `done`) unchanged.

Acceptance
- `/chat` streams real LLM output token deltas.
- Citations still emitted after generation.
- Errors propagate via SSE `error` event.

### 1.2: LLM prompt + system message
- Add a configurable prompt template for RAG answers.
- Include guidance: answer from context only; cite sources if possible.

Acceptance
- Prompt can be adjusted by env var (e.g., `LLM_SYSTEM_PROMPT`).

### 1.3: LLM provider selection (runtime)
- Support switching LLM provider via env (`LLM_PROVIDER=hf_local|tgi`).
- Validate provider initialization at startup (similar to embeddings check).

Acceptance
- API fails fast if provider misconfigured.

## Milestone 2 — LLM UX parity (UI/UX)
### 2.1: LLM settings panel
- Add inputs for model name and base URL (for TGI / local setup).
- Add a "Test Connection" button (like rag_demo’s Ollama test).
 - Persist LLM settings client-side (localStorage) so they survive refreshes.
 - Allow chat requests to override the server default LLM via provider/model/base URL.

Acceptance
- Users can verify LLM availability from the UI.

### 2.2: Chat controls parity
- Add top-k control and advanced retrieval toggle.
- If advanced retrieval is not implemented yet, disable the toggle with tooltip.

Acceptance
- Chat page mirrors rag_demo’s main controls layout.

### 2.3: Q&A history
- Persist and display recent Q&A (client-side for now).

Acceptance
- Last 5 questions visible with expandable answers.

## Milestone 3 — Retrieval enhancements (UI + backend follow-on)
### 3.1: Query reformulation + RRF (backend)
- Implement optional query reformulation and RRF rerank in `retrieve_top_k`.
- Expose `use_reranking` and `top_k` in `/chat` payload.

Acceptance
- When enabled, results are reranked; when disabled, behavior matches current.

### 3.2: Surface reformulations in UI
- Display generated reformulations under the answer.

Acceptance
- Visible to user when reranking is enabled.

## Milestone 4 — Ingestion UX parity (secondary)
- Add PDF support to upload.
- Add chunking configuration (size/overlap) in UI.
- Add embedder selection at upload (already present) plus validation.

Acceptance
- PDF upload works end-to-end; chunk config changes applied on ingest.

## Open Questions
- Should we prioritize local HF model loading or external TGI first?
- Do we want to keep the current “hash” embedder for demo mode?
- Is there an existing UI design system to align with?

## Suggested Order of Execution
1) Milestone 1 (LLM integration)
2) Milestone 2 (UI/UX parity for LLM controls)
3) Milestone 3 (retrieval upgrades)
4) Milestone 4 (ingestion UX parity)
