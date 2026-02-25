import logging
import os
from contextlib import contextmanager
from time import perf_counter
from typing import Any

from fastapi import HTTPException

from app.chat.chat_errors import chat_error_code
from app.chat.chat_models import ChatExecutionContext, ChatRequest
from app.core.retrieval_flags import resolve_advanced_retrieval_config
from app.providers.factory import get_llm_provider
from app.providers.llm.ollama_local import OllamaLocal
from app.providers.llm.openai_llm import OpenAILLM
from app.rag.retriever import retrieve_chunks
from app.rag.retrieval_strategy import resolve_retrieval_plan

logger = logging.getLogger(__name__)


def build_llm_provider(provider: str | None, model: str | None, base_url: str | None):
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

    raise HTTPException(status_code=400, detail=f"Unknown LLM provider: {provider_name}")


def select_llm(params: ChatRequest) -> Any:
    if params.llm_provider or params.llm_model or params.llm_base_url:
        return build_llm_provider(params.llm_provider, params.llm_model, params.llm_base_url)
    return get_llm_provider()


def extract_query(llm: Any, params: ChatRequest) -> str:
    return llm.latest_user_text([m.model_dump() for m in params.messages])


def retrieve_chunks_for_request(params: ChatRequest, query: str, retrieval_plan):
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


def build_log_context(
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


def build_chat_execution_context(payload: dict, request_id: str) -> ChatExecutionContext:
    params = ChatRequest.model_validate(payload)
    advanced_cfg = resolve_advanced_retrieval_config(
        request_payload=params.model_dump(exclude_none=True),
        request_id=request_id,
    )
    retrieval_plan = resolve_retrieval_plan(
        request_use_reranking=params.use_reranking,
        advanced_cfg=advanced_cfg,
    )
    llm = select_llm(params)
    query = extract_query(llm, params)
    return ChatExecutionContext(
        params=params,
        llm=llm,
        query=query,
        advanced_cfg=advanced_cfg,
        retrieval_plan=retrieval_plan,
        log_ctx=build_log_context(
            params=params,
            llm=llm,
            advanced_cfg=advanced_cfg,
            retrieval_plan=retrieval_plan,
        ),
    )


@contextmanager
def run_stage(
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
                "error_code": chat_error_code(exc, stage),
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


def emit_chat_pipeline_summary(
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
