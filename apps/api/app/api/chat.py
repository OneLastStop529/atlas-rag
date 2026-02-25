import asyncio
import logging
from time import perf_counter
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.chat.chat_errors import chat_error_code, dependency_from_error_code
from app.chat.chat_service import (
    build_chat_execution_context,
    build_llm_provider,
    emit_chat_pipeline_summary,
    retrieve_chunks_for_request,
    run_stage,
)
from app.chat.chat_shadow import run_shadow_retrieval
from app.chat.chat_stream import sse, stream_llm_answer
from app.core.metrics import inc_chat_stream_lifecycle, inc_provider_failure
from app.core.observability import get_request_id, reset_request_id, set_request_id
from app.core.reliability import DependencyError
from app.rag.retriever import build_context, get_reformulations, to_citations
from app.rag.retrieval_strategy import resolve_shadow_retrieval_plan, should_run_shadow_eval

logger = logging.getLogger(__name__)
router = APIRouter()
CHAT_CONTEXT_MAX_CHARS = 4000


async def _event_stream(payload: dict, request_id: str) -> AsyncGenerator[str, None]:
    token = set_request_id(request_id)
    request_started_at = perf_counter()
    stage_timings_ms: dict[str, int] = {}
    failed_stage_ref: list[str | None] = [None]
    log_ctx: dict[str, Any] = {}

    try:
        inc_chat_stream_lifecycle(status="started")
        execution = build_chat_execution_context(payload, request_id)
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
        logger.info("chat_request_received", extra=log_ctx)

        if execution.retrieval_plan.use_reranking:
            with run_stage(
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

        with run_stage(
            stage="retrieve",
            stage_timings_ms=stage_timings_ms,
            log_ctx=log_ctx,
            failed_stage_ref=failed_stage_ref,
        ):
            chunks = retrieve_chunks_for_request(params, query, retrieval_plan)
        logger.info("retrieval_count", extra={"count": len(chunks), **log_ctx})

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
                run_shadow_retrieval(
                    retrieve_chunks_fn=retrieve_chunks_for_request,
                    set_request_id_fn=set_request_id,
                    reset_request_id_fn=reset_request_id,
                    params=params,
                    query=query,
                    primary_plan=execution.retrieval_plan,
                    primary_chunks=chunks,
                    primary_latency_ms=primary_latency_ms,
                    shadow_plan=shadow_plan,
                    request_id=request_id,
                    log_ctx=log_ctx,
                    timeout_ms=execution.advanced_cfg.adv_retrieval_eval_timeout_ms,
                    chat_context_max_chars=CHAT_CONTEXT_MAX_CHARS,
                )
            )

        with run_stage(
            stage="build_context",
            stage_timings_ms=stage_timings_ms,
            log_ctx=log_ctx,
            failed_stage_ref=failed_stage_ref,
        ):
            context = build_context(chunks, max_chars=CHAT_CONTEXT_MAX_CHARS)
        citations = to_citations(chunks)

        with run_stage(
            stage="generate",
            stage_timings_ms=stage_timings_ms,
            log_ctx=log_ctx,
            failed_stage_ref=failed_stage_ref,
        ):
            async for chunk in stream_llm_answer(llm=llm, query=query, context=context):
                yield chunk

        yield sse("citations", {"items": citations})
        yield sse("done", {"ok": True})
        inc_chat_stream_lifecycle(status="completed")
        emit_chat_pipeline_summary(
            status="ok",
            request_started_at=request_started_at,
            stage_timings_ms=stage_timings_ms,
            log_ctx=log_ctx,
        )
    except Exception as e:
        failed_stage = failed_stage_ref[0]
        error_code = chat_error_code(e, failed_stage)
        inc_chat_stream_lifecycle(status="failed")
        inc_provider_failure(
            dependency=dependency_from_error_code(error_code),
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
        emit_chat_pipeline_summary(
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

    llm = build_llm_provider(provider, model, base_url)

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
