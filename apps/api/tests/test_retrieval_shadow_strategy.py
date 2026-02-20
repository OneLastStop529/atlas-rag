import unittest

from app.core.retrieval_flags import AdvancedRetrievalConfig
from app.rag.retrieval_strategy import (
    RetrievalPlan,
    resolve_shadow_retrieval_plan,
    should_run_shadow_eval,
)


class RetrievalShadowStrategyTests(unittest.TestCase):
    def _cfg(self, mode: str, sample: int) -> AdvancedRetrievalConfig:
        return AdvancedRetrievalConfig(
            enabled=True,
            retrieval_strategy="advanced_hybrid",
            reranker_variant="rrf_simple",
            query_rewrite_policy="simple",
            rollout_percent=100,
            from_request_override=False,
            adv_retrieval_eval_mode=mode,
            adv_retrieval_eval_sample_percent=sample,
            adv_retrieval_eval_timeout_ms=2000,
        )

    def test_should_run_shadow_eval_off_mode(self):
        self.assertFalse(
            should_run_shadow_eval(
                advanced_cfg=self._cfg(mode="off", sample=100),
                request_id="rid-shadow-1",
            )
        )

    def test_should_run_shadow_eval_sampling_boundaries(self):
        self.assertFalse(
            should_run_shadow_eval(
                advanced_cfg=self._cfg(mode="shadow", sample=0),
                request_id="rid-shadow-2",
            )
        )
        self.assertTrue(
            should_run_shadow_eval(
                advanced_cfg=self._cfg(mode="shadow", sample=100),
                request_id="rid-shadow-3",
            )
        )

    def test_resolve_shadow_plan_from_baseline(self):
        primary = RetrievalPlan(
            advanced_enabled=False,
            retrieval_strategy="baseline",
            query_rewrite_policy="disabled",
            reranker_variant="rrf_simple",
            use_reranking=False,
        )
        shadow = resolve_shadow_retrieval_plan(primary)
        self.assertEqual(shadow.retrieval_strategy, "advanced_hybrid")
        self.assertTrue(shadow.use_reranking)

    def test_resolve_shadow_plan_from_advanced(self):
        primary = RetrievalPlan(
            advanced_enabled=True,
            retrieval_strategy="advanced_hybrid_rerank",
            query_rewrite_policy="simple",
            reranker_variant="cross_encoder",
            use_reranking=True,
        )
        shadow = resolve_shadow_retrieval_plan(primary)
        self.assertEqual(shadow.retrieval_strategy, "baseline")
        self.assertFalse(shadow.use_reranking)


if __name__ == "__main__":
    unittest.main()
