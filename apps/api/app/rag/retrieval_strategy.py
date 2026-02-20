from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.core.retrieval_flags import AdvancedRetrievalConfig


@dataclass(frozen=True)
class RetrievalPlan:
    advanced_enabled: bool
    retrieval_strategy: str
    query_rewrite_policy: str
    reranker_variant: str
    use_reranking: bool


def resolve_retrieval_plan(
    *,
    request_use_reranking: bool,
    advanced_cfg: AdvancedRetrievalConfig,
) -> RetrievalPlan:
    strategy = advanced_cfg.retrieval_strategy
    use_reranking = request_use_reranking

    if advanced_cfg.enabled and strategy in {
        "advanced_hybrid",
        "advanced_hybrid_rerank",
    }:
        # Advanced strategies are always multi-query + fusion in this phase.
        use_reranking = True

    return RetrievalPlan(
        advanced_enabled=advanced_cfg.enabled,
        retrieval_strategy=strategy,
        query_rewrite_policy=advanced_cfg.query_rewrite_policy,
        reranker_variant=advanced_cfg.reranker_variant,
        use_reranking=use_reranking,
    )


def resolve_shadow_retrieval_plan(primary_plan: RetrievalPlan) -> RetrievalPlan:
    if primary_plan.retrieval_strategy in {"advanced_hybrid", "advanced_hybrid_rerank"}:
        return RetrievalPlan(
            advanced_enabled=False,
            retrieval_strategy="baseline",
            query_rewrite_policy="disabled",
            reranker_variant=primary_plan.reranker_variant,
            use_reranking=False,
        )

    return RetrievalPlan(
        advanced_enabled=True,
        retrieval_strategy="advanced_hybrid",
        query_rewrite_policy=(
            primary_plan.query_rewrite_policy
            if primary_plan.query_rewrite_policy != "disabled"
            else "simple"
        ),
        reranker_variant=primary_plan.reranker_variant,
        use_reranking=True,
    )


def should_run_shadow_eval(
    *, advanced_cfg: AdvancedRetrievalConfig, request_id: str | None
) -> bool:
    if advanced_cfg.adv_retrieval_eval_mode != "shadow":
        return False

    sample_percent = int(advanced_cfg.adv_retrieval_eval_sample_percent or 0)
    if sample_percent <= 0:
        return False
    if sample_percent >= 100:
        return True

    seed = request_id or "anonymous"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100
    return bucket < sample_percent
