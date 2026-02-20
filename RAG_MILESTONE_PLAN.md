# Atlas RAG Catch-up Plan (LLM First, then UI/UX)

## Goals
- Replace the v0 deterministic synthesizer with real LLM streaming.
- Preserve existing retrieval + citations while improving answer quality.
- Bring the web UI to parity with rag_demo’s controls and usability.

## Milestone 0 — Baseline & Safety (prep)
- Confirm current chat endpoint contract and SSE events.
- Add basic error handling and timeouts around LLM calls.
- Document env vars for LLM provider selection in one place.
 - Defer Prometheus-style metrics to a later milestone (use lightweight logs for now).

Status: ✅ Completed

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

Status: ✅ Completed

### 1.2: LLM prompt + system message
- Add a configurable prompt template for RAG answers.
- Include guidance: answer from context only; cite sources if possible.

Acceptance
- Prompt can be adjusted by env var (e.g., `LLM_SYSTEM_PROMPT`).

Status: ✅ Completed

### 1.3: LLM provider selection (runtime)
- Support switching LLM provider via env (`LLM_PROVIDER=hf_local|tgi`).
- Validate provider initialization at startup (similar to embeddings check).

Acceptance
- API fails fast if provider misconfigured.

Status: ✅ Completed

## Milestone 2 — LLM UX parity (UI/UX)
### 2.1: LLM settings panel
- Add inputs for model name and base URL (for TGI / local setup).
- Add a "Test Connection" button (like rag_demo’s Ollama test).
 - Persist LLM settings client-side (localStorage) so they survive refreshes.
 - Allow chat requests to override the server default LLM via provider/model/base URL.

Acceptance
- Users can verify LLM availability from the UI.

Status: ✅ Completed

### 2.2: Chat controls parity
- Add top-k control and advanced retrieval toggle.
- If advanced retrieval is not implemented yet, disable the toggle with tooltip.

Acceptance
- Chat page mirrors rag_demo’s main controls layout.

Status: ✅ Completed

### 2.3: Q&A history
- Persist and display recent Q&A (client-side for now).

Acceptance
- Last 5 questions visible with expandable answers.

Status: ✅ Completed

## Milestone 3 — Retrieval enhancements (UI + backend follow-on)
### 3.1: Query reformulation + RRF (backend)
- Implement optional query reformulation and RRF rerank in `retrieve_top_k`.
- Expose `use_reranking` and `top_k` in `/chat` payload.

Acceptance
- When enabled, results are reranked; when disabled, behavior matches current.

Status: ✅ Completed

### 3.2: Surface reformulations in UI
- Display generated reformulations under the answer.

Acceptance
- Visible to user when reranking is enabled.

Status: ✅ Completed

## Milestone 4 — Ingestion UX parity (secondary)
- Add PDF support to upload.
- Add chunking configuration (size/overlap) in UI.
- Add embedder selection at upload (already present) plus validation.

Acceptance
- PDF upload works end-to-end; chunk config changes applied on ingest.

Status: ✅ Completed
Notes:
- Backend PDF upload support is complete.
- UI chunk config controls are implemented and wired to upload payload.
- Upload embedder selection supports provider options and structured field-level validation errors.
- Validation envelope regression tests added: `apps/api/tests/test_upload_validation.py` (3 tests, passing).
- Smoke verification:
  - `apps/api/scripts/test_upload.py` passes.
  - `apps/api/scripts/retrieve_smoke.py` and `apps/api/scripts/pgvector_smoke.py` currently fail with DB connectivity (`psycopg2.OperationalError`) in this environment.

## Milestone 5 — Retrieval + Infra Hardening (observability/reliability first)
### 5.1: Reliability baseline (first)
- Add explicit timeouts/retries/circuit-breaker behavior across retrieval and embedding calls.
- Add startup/runtime dependency health checks (DB, vector extension, embeddings provider).
- Add failure-mode tests for degraded paths (provider down, DB unavailable, bad payloads).

Acceptance
- Service fails fast on hard dependency misconfiguration.
- Common transient failures are retried with bounded backoff and clear error responses.
- Smoke suite has stable pass/fail signals for healthy vs degraded environments.

Status: ✅ Completed
Notes:
- Added retry/backoff + timeout-budget utilities in `apps/api/app/core/reliability.py`.
- Wired retrieval/upload/embeddings paths to use bounded retries and DB statement/connect timeouts.
- Added startup dependency validation + readiness/liveness endpoints in `apps/api/app/main.py`.
- Added reliability + health regression tests in `apps/api/tests/test_reliability_health.py`.

### 5.2: Observability baseline (second)
- 5.2.1 Logging foundation
  - Add request correlation middleware (request ID from `X-Request-ID`, fallback generated UUID).
  - Emit JSON structured logs for each request with route, method, status, latency_ms, request_id.
  - Include shared context keys in logs: `request_id`, `collection_id`, `embeddings_provider`, `llm_provider`.
- 5.2.2 Stage instrumentation
  - Add stage timers around `retrieve`, `rerank`, `build_context`, `generate`, and `upload_ingest`.
  - Emit one summary event per request (`chat_pipeline_summary`, `upload_pipeline_summary`) plus per-stage events.
  - Add explicit dependency failure events with normalized codes (`db_timeout`, `embeddings_unavailable`, `llm_stream_error`).
- 5.2.3 Metrics surface
  - Add Prometheus metrics endpoint (or equivalent exporter) with:
    - Request counter by route/status.
    - Request latency histogram for chat/upload.
    - Provider error counters by dependency + error code.
    - Ingestion throughput counter (files/chunks processed).
  - Track SSE chat lifecycle metrics (`chat_stream_started`, `chat_stream_completed`, `chat_stream_failed`).
- 5.2.4 Dashboards + alerts
  - Create a minimal dashboard for API and ingestion:
    - p50/p95/p99 latency for `/api/chat` and `/api/upload`.
    - Error rate by endpoint and provider failures.
    - Readiness failures over time.
  - Define alert thresholds:
    - Error rate > 5% for 5m.
    - p95 latency > 3s for chat for 10m.
    - Any sustained readiness failure > 2m.
- 5.2.5 Validation + rollout
  - Add tests for request ID propagation and metric increments on success/failure paths.
  - Add smoke script that runs one chat and one upload request, then verifies log correlation + metric exposure.
  - Roll out behind env flags (`OBS_LOGS_ENABLED`, `OBS_METRICS_ENABLED`) default-on in dev/stage.

Acceptance
- A single request can be traced end-to-end from logs.
- Latency and error SLO indicators are visible for chat and upload APIs.
- A smoke check confirms request correlation + metric updates for both happy and degraded paths.

Status: 🚧 In Progress
Next execution order:
1) Logging foundation + request IDs
2) Stage instrumentation (chat + upload)
3) Metrics endpoint and counters/histograms
4) Dashboard + alert rules
5) Tests and smoke verification
Progress notes:
- ✅ Step 1 complete: request correlation middleware + structured JSON logs.
- ✅ Step 2 complete: stage-level timing/failure logs and per-pipeline summaries.
- ✅ Step 3 complete: `/metrics` endpoint, request/error/latency counters, SSE lifecycle metrics.
- ✅ Step 4 complete: Grafana + Prometheus OSS scaffold, dashboard, and alert rules.
- ✅ Step 5 implementation added: request-ID + metrics regression tests and observability smoke script.

### 5.3: Advanced retrieval rollout (third, behind flags)
- Add feature-flagged advanced retrieval options (hybrid retrieval, reranker variants, query rewriting policy).
- Run side-by-side evaluation (baseline vs advanced) with quality/latency/cost tracking.
- Enable progressive rollout by environment or traffic percentage.

Acceptance
- Advanced retrieval can be toggled safely without deploy rollback.
- Evaluation reports show quality delta and latency/cost impact before broad rollout.

Status: ⏳ Planned

5.3 Closeout Checklist
- [ ] Aggregate `retrieval_shadow_eval` into a report/dashboard (quality overlap, latency deltas, sample size).
- [ ] Add per-request cost proxies to shadow eval output and baseline vs advanced cost deltas.
- [ ] Define environment defaults (`dev`, `staging`, `prod`) for rollout/eval flags and document promotion gates.
- [ ] Smoke-test advanced retrieval toggle safety (off/on) without deploy rollback.
- [ ] Run E2E scenarios for baseline-only, sampled shadow eval, and rollout at 0%/partial/100%.
- [ ] Attach closeout evidence (test results, smoke commands, dashboard/report links) and mark 5.3 complete.

### 5.4: Infra deployment hardening (fourth)
- Standardize deployment checks: readiness/liveness probes, startup sequencing, and config validation.
- Add runbooks for common incidents (provider outage, vector DB issues, queue backlogs).
- Add rollback playbook and release gates tied to error/latency thresholds.

Acceptance
- Deployments have automated health gating and deterministic rollback steps.
- On-call has documented runbooks for top failure classes.

Status: ⏳ Planned

### 5.5: Optimization pass (after stability)
- Profile hot paths and tune chunking/retrieval defaults based on observed production metrics.
- Optimize only after reliability/observability signals are stable.

Acceptance
- Changes show measurable improvement without SLO regressions.

Status: ⏳ Planned

## Open Questions
- Should we prioritize local HF model loading or external TGI first?
- Do we want to keep the current “hash” embedder for demo mode?
- Is there an existing UI design system to align with?
- Defer investigating non-deterministic LLM responses (e.g., “I don’t know” on first query) to a later milestone.

## Suggested Order of Execution
1) Milestone 1 (LLM integration)
2) Milestone 2 (UI/UX parity for LLM controls)
3) Milestone 3 (retrieval upgrades)
4) Milestone 4 (ingestion UX parity)
5) Milestone 5 (retrieval + infra hardening with reliability/observability first)
