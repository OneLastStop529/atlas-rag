from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping

from app.config import settings

ALLOWED_RETRIEVAL_STRATEGIES = {
    "baseline",
    "advanced_hybrid",
    "advanced_hybrid_rerank",
}
ALLOWED_RERANKER_VARIANTS = {
    "rrf_simple",
    "cross_encoder",
}
ALLOWED_QUERY_REWRITE_POLICIES = {
    "disabled",
    "simple",
    "llm",
}


@dataclass(frozen=True)
class AdvancedRetrievalConfig:
    enabled: bool
    retrieval_strategy: str
    reranker_variant: str
    query_rewrite_policy: str
    rollout_percent: int
    from_request_override: bool


def resolve_advanced_retrieval_config(
    *,
    request_payload: Mapping[str, Any] | None,
    request_id: str | None,
) -> AdvancedRetrievalConfig:
    raw_enabled = settings.adv_retrieval_enabled
    raw_strategy = settings.retrieval_strategy
    raw_reranker = settings.reranker_variant
    raw_rewrite_policy = settings.query_rewrite_policy
    raw_rollout_percent = settings.adv_retrieval_rollout_percent
    used_request_override = False

    payload = request_payload or {}
    if settings.adv_retrieval_allow_request_override:
        if "adv_retrieval_enabled" in payload:
            raw_enabled = bool(payload.get("adv_retrieval_enabled"))
            used_request_override = True
        if payload.get("retrieval_strategy"):
            raw_strategy = str(payload["retrieval_strategy"])
            used_request_override = True
        if payload.get("reranker_variant"):
            raw_reranker = str(payload["reranker_variant"])
            used_request_override = True
        if payload.get("query_rewrite_policy"):
            raw_rewrite_policy = str(payload["query_rewrite_policy"])
            used_request_override = True

    strategy = _normalize_enum(
        raw_value=raw_strategy,
        allowed_values=ALLOWED_RETRIEVAL_STRATEGIES,
        fallback="baseline",
    )
    reranker_variant = _normalize_enum(
        raw_value=raw_reranker,
        allowed_values=ALLOWED_RERANKER_VARIANTS,
        fallback="rrf_simple",
    )
    query_rewrite_policy = _normalize_enum(
        raw_value=raw_rewrite_policy,
        allowed_values=ALLOWED_QUERY_REWRITE_POLICIES,
        fallback="disabled",
    )
    rollout_percent = _clamp_rollout_percent(raw_rollout_percent)
    rollout_enabled = _rollout_enabled(
        request_id=request_id,
        rollout_percent=rollout_percent,
    )

    return AdvancedRetrievalConfig(
        enabled=bool(raw_enabled) and rollout_enabled,
        retrieval_strategy=strategy,
        reranker_variant=reranker_variant,
        query_rewrite_policy=query_rewrite_policy,
        rollout_percent=rollout_percent,
        from_request_override=used_request_override,
    )


def _normalize_enum(
    *, raw_value: Any, allowed_values: set[str], fallback: str
) -> str:
    value = str(raw_value or "").strip().lower()
    if value in allowed_values:
        return value
    return fallback


def _clamp_rollout_percent(raw_percent: Any) -> int:
    try:
        parsed = int(raw_percent)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, parsed))


def _rollout_enabled(*, request_id: str | None, rollout_percent: int) -> bool:
    if rollout_percent <= 0:
        return False
    if rollout_percent >= 100:
        return True

    seed = request_id or "anonymous"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return bucket < rollout_percent
