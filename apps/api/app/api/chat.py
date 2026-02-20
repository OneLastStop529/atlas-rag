import json
import logging
import os
import asyncio
from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter
from typing import Any, AsyncGenerator, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Literal

from app.core.observability import get_request_id, reset_request_id, set_request_id
from app.core.metrics import inc_chat_stream_lifecycle, inc_provider_failure
from app.core.retrieval_flags import resolve_advanced_retrieval_config
from app.providers.factory import get_llm_provider
from app.providers.llm.openai_llm import OpenAILLM
from app.providers.llm.ollama_local import OllamaLocal
from app.core.reliability import DependencyError
from app.rag.retriever import build_context, retrieve_chunks, to_citations, get_reformulations
from app.rag.retrievers.types import RetrievedChunk
from app.rag.retrieval_strategy import (
    resolve_retrieval_plan,
    resolve_shadow_retrieval_plan,
    should_run_shadow_eval,
)


logger = logging.getLogger(__name__)
router = APIRouter()


def sse(event: str, data: dict) -> str:
    """Format data as Server-Sent Events (SSE)."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    collection_id: str = "default"
    messages: List[ChatMessage] = Field(default_factory=list)
    k: int = Field(default=5, ge=1, le=50)
    embeddings_provider: Optional[str] = None
    retriever_provider: Optional[str] = None
    use_reranking: bool = False
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None
    adv_retrieval_enabled: Optional[bool] = None
    retrieval_strategy: Optional[str] = None
    reranker_variant: Optional[str] = None
    query_rewrite_policy: Optional[str] = None
    adv_retrieval_eval_mode: Optional[str] = None
    adv_retrieval_eval_sample_percent: Optional[int] = None
    adv_retrieval_eval_timeout_ms: Optional[int] = None


def _build_llm_provider(provider: str | None, model: str | None, base_url: str | None):
    provider_name = (provider or os.getenv("LLM_PROVIDER", "ollama")).strip().lower()
    if provider_name == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=400, detail="OPENAI_API_KEY is required for OpenAI tests."
            )
        model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        base_url = base_url or os.getenv("OPENAI_BASE_URL")
        return OpenAILLM(api_key=api_key, model=model, base_url=base_url)

    if provider_name in {"ollama", "ollama_local"}:
        model = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        base_url = base_url or os.getenv("OLLAMA_BASE_URL")
        return OllamaLocal(model=model, base_url=base_url)

    raise HTTPException(
        status_code=400, detail=f"Unknown LLM provider: {provider_name}"
    )


def _select_llm(params: ChatRequest) -> Any:
    if params.llm_provider or params.llm_model or params.llm_base_url:
        return _build_llm_provider(
            params.llm_provider, params.llm_model, params.llm_base_url
        )
    return get_llm_provider()


def _extract_query(llm: Any, params: ChatRequest) -> str:
    return llm.latest_user_text([m.model_dump() for m in params.messages])


def _retrieve_chunks(params: ChatRequest, query: str, retrieval_plan):
    embeddings_provider = params.embeddings_provider or "hash"
    return retrieve_chunks(
        query=query,
        collection_id=params.collection_id,
        k=params.k,
        embeddings_provider=embeddings_provider,
        retriever_provider=params.retriever_provider,
        use_reranking=retrieval_plan.use_reranking,
        retrieval_strategy=retrieval_plan.retrieval_strategy,
        query_rewrite_policy=retrieval_plan.query_rewrite_policy,
        reranker_variant=retrieval_plan.reranker_variant,
        advanced_enabled=retrieval_plan.advanced_enabled,
    )


async def _stream_llm_answer(
    *, llm, query: str, context: str
) -> AsyncGenerator[str, None]:
    llm_messages = llm.build_llm_messages(query=query, context=context)
    async for chunk in llm.stream_chat(llm_messages):
        delta = chunk.get("delta")
        if delta:
            yield sse("token", {"delta": delta})


def _chat_error_code(exc: Exception, stage: str | None) -> str:
    message = str(exc).lower()
    if stage == "generate":
        return "llm_stream_error"
    if "embed" in message:
        return "embeddings_unavailable"
    if "timeout" in message or "statement_timeout" in message:
        return "db_timeout"
    if isinstance(exc, DependencyError):
        return "dependency_unavailable"
    return "chat_pipeline_error"


def _dependency_from_error_code(error_code: str) -> str:
    if error_code == "llm_stream_error":
        return "llm"
    if error_code == "embeddings_unavailable":
        return "embeddings"
    if error_code == "db_timeout":
        return "db"
    return "chat"


@dataclass(frozen=True)
class ChatExecutionContext:
    params: ChatRequest
    llm: Any
    query: str
    advanced_cfg: Any
    retrieval_plan: Any
    log_ctx: dict[str, Any]


def _build_log_context(
    *, params: ChatRequest, llm: Any, advanced_cfg: Any, retrieval_plan: Any
) -> dict[str, Any]:
    return {
        "collection_id": params.collection_id,
        "embeddings_provider": params.embeddings_provider or "hash",
        "llm_provider": getattr(llm, "name", None),
        "adv_retrieval_enabled": advanced_cfg.enabled,
        "retrieval_strategy": advanced_cfg.retrieval_strategy,
        "reranker_variant": advanced_cfg.reranker_variant,
        "query_rewrite_policy": advanced_cfg.query_rewrite_policy,
        "adv_retrieval_rollout_percent": advanced_cfg.rollout_percent,
        "adv_retrieval_eval_mode": advanced_cfg.adv_retrieval_eval_mode,
        "adv_retrieval_eval_sample_percent": advanced_cfg.adv_retrieval_eval_sample_percent,
        "adv_retrieval_eval_timeout_ms": advanced_cfg.adv_retrieval_eval_timeout_ms,
        "use_reranking_effective": retrieval_plan.use_reranking,
    }


def _build_chat_execution_context(payload: dict, request_id: str) -> ChatExecutionContext:
    params = ChatRequest.model_validate(payload)
    advanced_cfg = resolve_advanced_retrieval_config(
        request_payload=params.model_dump(exclude_none=True),
        request_id=request_id,
    )
    retrieval_plan = resolve_retrieval_plan(
        request_use_reranking=params.use_reranking,
        advanced_cfg=advanced_cfg,
    )
    llm = _select_llm(params)
    query = _extract_query(llm, params)
    return ChatExecutionContext(
        params=params,
        llm=llm,
        query=query,
        advanced_cfg=advanced_cfg,
        retrieval_plan=retrieval_plan,
        log_ctx=_build_log_context(
            params=params,
            llm=llm,
            advanced_cfg=advanced_cfg,
            retrieval_plan=retrieval_plan,
        ),
    )


@contextmanager
def _run_stage(
    *,
    stage: str,
    stage_timings_ms: dict[str, int],
    log_ctx: dict[str, Any],
    failed_stage_ref: list[str | None],
):
    started_at = perf_counter()
    try:
        yield
    except Exception as exc:
        failed_stage_ref[0] = stage
        duration_ms = int((perf_counter() - started_at) * 1000)
        logger.exception(
            "chat_stage_failed",
            extra={
                "stage": stage,
                "duration_ms": duration_ms,
                "error_code": _chat_error_code(exc, stage),
                **log_ctx,
            },
        )
        raise
    else:
        duration_ms = int((perf_counter() - started_at) * 1000)
        stage_timings_ms[stage] = duration_ms
        logger.info(
            "chat_stage_completed",
            extra={"stage": stage, "duration_ms": duration_ms, **log_ctx},
        )


def _emit_chat_pipeline_summary(
    *,
    status: str,
    request_started_at: float,
    stage_timings_ms: dict[str, int],
    log_ctx: dict[str, Any],
    failed_stage: str | None = None,
    error_code: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "status": status,
        "stages_ms": stage_timings_ms,
        "total_latency_ms": int((perf_counter() - request_started_at) * 1000),
        **log_ctx,
    }
    if failed_stage is not None:
        payload["failed_stage"] = failed_stage
    if error_code is not None:
        payload["error_code"] = error_code
    logger.info("chat_pipeline_summary", extra=payload)


async def _run_shadow_retrieval(
    *,
    params: ChatRequest,
    query: str,
    primary_plan: Any,
    primary_chunks: list[RetrievedChunk],
    primary_latency_ms: int,
    shadow_plan: Any,
    request_id: str,
    log_ctx: dict[str, Any],
    timeout_ms: int,
) -> None:
    token = set_request_id(request_id)
    started_at = perf_counter()
    try:
        shadow_chunks = await asyncio.wait_for(
            asyncio.to_thread(_retrieve_chunks, params, query, shadow_plan),
            timeout=timeout_ms / 1000.0,
        )
        _emit_retrieval_shadow_eval(
            primary_plan=primary_plan,
            primary_chunks=primary_chunks,
            primary_latency_ms=primary_latency_ms,
            shadow_plan=shadow_plan,
            shadow_chunks=shadow_chunks,
            shadow_latency_ms=int((perf_counter() - started_at) * 1000),
            status="ok",
            log_ctx=log_ctx,
        )
    except Exception as exc:
        logger.exception("retrieval_shadow_failed", extra={"shadow_error": str(exc), **log_ctx})
        _emit_retrieval_shadow_eval(
            primary_plan=primary_plan,
            primary_chunks=primary_chunks,
            primary_latency_ms=primary_latency_ms,
            shadow_plan=shadow_plan,
            shadow_chunks=[],
            shadow_latency_ms=int((perf_counter() - started_at) * 1000),
            status="error",
            shadow_error=str(exc),
            log_ctx=log_ctx,
        )
    finally:
        reset_request_id(token)


def _emit_retrieval_shadow_eval(
    *,
    primary_plan: Any,
    primary_chunks: list[RetrievedChunk],
    primary_latency_ms: int,
    shadow_plan: Any,
    shadow_chunks: list[RetrievedChunk],
    shadow_latency_ms: int,
    status: str,
    log_ctx: dict[str, Any],
    shadow_error: str | None = None,
) -> None:
    primary_ids = _chunk_ids(primary_chunks)
    shadow_ids = _chunk_ids(shadow_chunks)
    shared_ids = len(primary_ids & shadow_ids)
    union_ids = len(primary_ids | shadow_ids)
    jaccard = (shared_ids / union_ids) if union_ids else 0.0

    logger.info(
        "retrieval_shadow_eval",
        extra={
            "status": status,
            "primary_strategy": primary_plan.retrieval_strategy,
            "shadow_strategy": shadow_plan.retrieval_strategy,
            "primary_use_reranking": primary_plan.use_reranking,
            "shadow_use_reranking": shadow_plan.use_reranking,
            "primary_count": len(primary_chunks),
            "shadow_count": len(shadow_chunks),
            "shared_chunk_ids": shared_ids,
            "jaccard": round(jaccard, 4),
            "primary_latency_ms": primary_latency_ms,
            "shadow_latency_ms": shadow_latency_ms,
            "top1_source_same": _top1_source_same(primary_chunks, shadow_chunks),
            "shadow_error": shadow_error,
            **log_ctx,
        },
    )


def _chunk_ids(chunks: list[RetrievedChunk]) -> set[str]:
    ids: set[str] = set()
    for chunk in chunks:
        if chunk.chunk_id:
            ids.add(chunk.chunk_id)
    return ids


def _top1_source_same(
    primary_chunks: list[RetrievedChunk], shadow_chunks: list[RetrievedChunk]
) -> bool:
    if not primary_chunks or not shadow_chunks:
        return False
    return primary_chunks[0].source == shadow_chunks[0].source


async def _event_stream(payload: dict, request_id: str) -> AsyncGenerator[str, None]:
    token = set_request_id(request_id)
    request_started_at = perf_counter()
    stage_timings_ms: dict[str, int] = {}
    failed_stage_ref: list[str | None] = [None]
    log_ctx: dict[str, Any] = {}

    try:
        inc_chat_stream_lifecycle(status="started")
        execution = _build_chat_execution_context(payload, request_id)
        params = execution.params
        retrieval_plan = execution.retrieval_plan
        query = execution.query
        llm = execution.llm
        log_ctx = execution.log_ctx

        if not execution.query:
            yield sse("error", {"message": "No user query found in messages"})
            yield sse("done", {})
            return

        logger.debug("chat_params", extra={"params": params.model_dump()})
        logger.info(
            "chat_request_received",
            extra=log_ctx,
        )

        if execution.retrieval_plan.use_reranking:
            with _run_stage(
                stage="rerank",
                stage_timings_ms=stage_timings_ms,
                log_ctx=log_ctx,
                failed_stage_ref=failed_stage_ref,
            ):
                reformulations = get_reformulations(
                    query,
                    use_reranking=execution.retrieval_plan.use_reranking,
                    query_rewrite_policy=execution.retrieval_plan.query_rewrite_policy,
                )
            yield sse("reformulations", {"items": reformulations})

        with _run_stage(
            stage="retrieve",
            stage_timings_ms=stage_timings_ms,
            log_ctx=log_ctx,
            failed_stage_ref=failed_stage_ref,
        ):
            chunks = _retrieve_chunks(params, query, retrieval_plan)
        logger.info(
            "retrieval_count",
            extra={
                "count": len(chunks),
                **log_ctx,
            },
        )

        if should_run_shadow_eval(
            advanced_cfg=execution.advanced_cfg,
            request_id=request_id,
        ):
            shadow_plan = resolve_shadow_retrieval_plan(execution.retrieval_plan)
            primary_latency_ms = stage_timings_ms.get("retrieve", 0)
            logger.info(
                "retrieval_shadow_started",
                extra={
                    "primary_strategy": execution.retrieval_plan.retrieval_strategy,
                    "shadow_strategy": shadow_plan.retrieval_strategy,
                    "shadow_timeout_ms": execution.advanced_cfg.adv_retrieval_eval_timeout_ms,
                    **log_ctx,
                },
            )
            asyncio.create_task(
                _run_shadow_retrieval(
                    params=params,
                    query=query,
                    primary_plan=execution.retrieval_plan,
                    primary_chunks=chunks,
                    primary_latency_ms=primary_latency_ms,
                    shadow_plan=shadow_plan,
                    request_id=request_id,
                    log_ctx=log_ctx,
                    timeout_ms=execution.advanced_cfg.adv_retrieval_eval_timeout_ms,
                )
            )

        with _run_stage(
            stage="build_context",
            stage_timings_ms=stage_timings_ms,
            log_ctx=log_ctx,
            failed_stage_ref=failed_stage_ref,
        ):
            context = build_context(chunks, max_chars=4000)
        citations = to_citations(chunks)

        with _run_stage(
            stage="generate",
            stage_timings_ms=stage_timings_ms,
            log_ctx=log_ctx,
            failed_stage_ref=failed_stage_ref,
        ):
            async for chunk in _stream_llm_answer(llm=llm, query=query, context=context):
                yield chunk

        yield sse("citations", {"items": citations})
        yield sse("done", {"ok": True})
        inc_chat_stream_lifecycle(status="completed")
        _emit_chat_pipeline_summary(
            status="ok",
            request_started_at=request_started_at,
            stage_timings_ms=stage_timings_ms,
            log_ctx=log_ctx,
        )
    except Exception as e:
        failed_stage = failed_stage_ref[0]
        error_code = _chat_error_code(e, failed_stage)
        inc_chat_stream_lifecycle(status="failed")
        inc_provider_failure(
            dependency=_dependency_from_error_code(error_code),
            error_code=error_code,
        )
        logger.error(
            "chat_dependency_failure",
            extra={
                "stage": failed_stage or "unknown",
                "error_code": error_code,
                "error": str(e),
                **log_ctx,
            },
        )
        _emit_chat_pipeline_summary(
            status="error",
            failed_stage=failed_stage or "unknown",
            error_code=error_code,
            request_started_at=request_started_at,
            stage_timings_ms=stage_timings_ms,
            log_ctx=log_ctx,
        )
        if isinstance(e, DependencyError):
            yield sse(
                "error",
                {
                    "message": str(e),
                    "retryable": e.retryable,
                    "code": "DEPENDENCY_ERROR",
                },
            )
        else:
            yield sse("error", {"message": str(e)})
        yield sse("done", {"ok": False})
    finally:
        reset_request_id(token)


@router.post("/api/chat")
async def chat(payload: dict, request: Request):
    """
    Expected paylod:
        {
            "collection_id": "default",
            "messages": [{"role": "user", "content": "..."}],
            "k": 5,
            "embeddings_provider": "hash" | "sentence-transformers",
        }
    """
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }

    return StreamingResponse(
        _event_stream(payload, request_id=get_request_id()),
        headers=headers,
        media_type="text/event-stream",
    )


@router.post("/api/llm/test")
async def test_llm(payload: dict):
    provider = payload.get("provider")
    model = payload.get("model")
    base_url = payload.get("base_url")
    messages = payload.get("messages") or [{"role": "user", "content": "ping"}]
    max_tokens = payload.get("max_tokens") or 8

    llm = _build_llm_provider(provider, model, base_url)

    try:
        sample = ""
        async for chunk in llm.stream_chat(messages, max_tokens=max_tokens):
            delta = chunk.get("delta")
            if delta:
                sample = delta
                break
        return {"ok": True, "provider": llm.name, "sample": sample}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
