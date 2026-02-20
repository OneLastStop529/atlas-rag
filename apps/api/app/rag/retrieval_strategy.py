from __future__ import annotations

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
