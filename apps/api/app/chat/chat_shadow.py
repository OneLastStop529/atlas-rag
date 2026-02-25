import asyncio
import logging
from time import perf_counter
from typing import Any, Callable

from app.core.metrics import observe_retrieval_shadow_eval
from app.rag.retrievers.types import RetrievedChunk

logger = logging.getLogger(__name__)


def emit_retrieval_shadow_eval(
    *,
    primary_plan: Any,
    primary_chunks: list[RetrievedChunk],
    primary_latency_ms: int,
    shadow_plan: Any,
    shadow_chunks: list[RetrievedChunk],
    shadow_latency_ms: int,
    status: str,
    log_ctx: dict[str, Any],
    chat_context_max_chars: int,
    shadow_error: str | None = None,
) -> None:
    primary_ids = _chunk_ids(primary_chunks)
    shadow_ids = _chunk_ids(shadow_chunks)
    shared_ids = len(primary_ids & shadow_ids)
    union_ids = len(primary_ids | shadow_ids)
    jaccard = (shared_ids / union_ids) if union_ids else 0.0
    primary_context_chars, primary_context_chunks = _estimate_context_proxy(
        primary_chunks, chat_context_max_chars
    )
    shadow_context_chars, shadow_context_chunks = _estimate_context_proxy(
        shadow_chunks, chat_context_max_chars
    )
    primary_context_token_proxy = _chars_to_token_proxy(primary_context_chars)
    shadow_context_token_proxy = _chars_to_token_proxy(shadow_context_chars)

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
            "latency_delta_ms": shadow_latency_ms - primary_latency_ms,
            "top1_source_same": _top1_source_same(primary_chunks, shadow_chunks),
            "primary_context_chars": primary_context_chars,
            "shadow_context_chars": shadow_context_chars,
            "context_chars_delta": shadow_context_chars - primary_context_chars,
            "primary_context_token_proxy": primary_context_token_proxy,
            "shadow_context_token_proxy": shadow_context_token_proxy,
            "context_token_proxy_delta": shadow_context_token_proxy
            - primary_context_token_proxy,
            "primary_context_chunks": primary_context_chunks,
            "shadow_context_chunks": shadow_context_chunks,
            "context_chunks_delta": shadow_context_chunks - primary_context_chunks,
            "shadow_error": shadow_error,
            **log_ctx,
        },
    )
    observe_retrieval_shadow_eval(
        status=status,
        primary_strategy=primary_plan.retrieval_strategy,
        shadow_strategy=shadow_plan.retrieval_strategy,
        jaccard=jaccard,
        latency_delta_ms=shadow_latency_ms - primary_latency_ms,
        context_token_delta=shadow_context_token_proxy - primary_context_token_proxy,
        top1_source_same=_top1_source_same(primary_chunks, shadow_chunks),
    )


async def run_shadow_retrieval(
    *,
    retrieve_chunks_fn: Callable[[Any, str, Any], list[RetrievedChunk]],
    set_request_id_fn: Callable[[str], Any],
    reset_request_id_fn: Callable[[Any], None],
    params: Any,
    query: str,
    primary_plan: Any,
    primary_chunks: list[RetrievedChunk],
    primary_latency_ms: int,
    shadow_plan: Any,
    request_id: str,
    log_ctx: dict[str, Any],
    timeout_ms: int,
    chat_context_max_chars: int,
) -> None:
    token = set_request_id_fn(request_id)
    started_at = perf_counter()
    try:
        shadow_chunks = await asyncio.wait_for(
            asyncio.to_thread(retrieve_chunks_fn, params, query, shadow_plan),
            timeout=timeout_ms / 1000.0,
        )
        emit_retrieval_shadow_eval(
            primary_plan=primary_plan,
            primary_chunks=primary_chunks,
            primary_latency_ms=primary_latency_ms,
            shadow_plan=shadow_plan,
            shadow_chunks=shadow_chunks,
            shadow_latency_ms=int((perf_counter() - started_at) * 1000),
            status="ok",
            log_ctx=log_ctx,
            chat_context_max_chars=chat_context_max_chars,
        )
    except Exception as exc:
        logger.exception(
            "retrieval_shadow_failed", extra={"shadow_error": str(exc), **log_ctx}
        )
        emit_retrieval_shadow_eval(
            primary_plan=primary_plan,
            primary_chunks=primary_chunks,
            primary_latency_ms=primary_latency_ms,
            shadow_plan=shadow_plan,
            shadow_chunks=[],
            shadow_latency_ms=int((perf_counter() - started_at) * 1000),
            status="error",
            shadow_error=str(exc),
            log_ctx=log_ctx,
            chat_context_max_chars=chat_context_max_chars,
        )
    finally:
        reset_request_id_fn(token)


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


def _estimate_context_proxy(
    chunks: list[RetrievedChunk], chat_context_max_chars: int
) -> tuple[int, int]:
    used_chars = 0
    included_chunks = 0
    for chunk in chunks:
        header = f"[Source: {chunk.source} | Chunk: {chunk.chunk_index}]\n"
        block = header + chunk.content.strip()
        if used_chars + len(block) + 2 > chat_context_max_chars:
            break
        used_chars += len(block) + 2
        included_chunks += 1
    return used_chars, included_chunks


def _chars_to_token_proxy(char_count: int) -> int:
    return max(0, (char_count + 3) // 4)
