import unittest

from app.config import settings
from app.core.retrieval_flags import resolve_advanced_retrieval_config


class RetrievalFlagsTests(unittest.TestCase):
    def setUp(self):
        self._original = {
            "adv_retrieval_enabled": settings.adv_retrieval_enabled,
            "adv_retrieval_allow_request_override": settings.adv_retrieval_allow_request_override,
            "retrieval_strategy": settings.retrieval_strategy,
            "reranker_variant": settings.reranker_variant,
            "query_rewrite_policy": settings.query_rewrite_policy,
            "adv_retrieval_rollout_percent": settings.adv_retrieval_rollout_percent,
        }

    def tearDown(self):
        for key, value in self._original.items():
            setattr(settings, key, value)

    def test_defaults_to_baseline_when_disabled(self):
        settings.adv_retrieval_enabled = False
        settings.retrieval_strategy = "advanced_hybrid"
        settings.adv_retrieval_rollout_percent = 100

        cfg = resolve_advanced_retrieval_config(
            request_payload={},
            request_id="rid-1",
        )

        self.assertFalse(cfg.enabled)
        self.assertEqual(cfg.retrieval_strategy, "advanced_hybrid")

    def test_ignores_request_override_when_not_allowed(self):
        settings.adv_retrieval_enabled = True
        settings.adv_retrieval_allow_request_override = False
        settings.retrieval_strategy = "baseline"
        settings.adv_retrieval_rollout_percent = 100

        cfg = resolve_advanced_retrieval_config(
            request_payload={"retrieval_strategy": "advanced_hybrid"},
            request_id="rid-2",
        )

        self.assertTrue(cfg.enabled)
        self.assertEqual(cfg.retrieval_strategy, "baseline")
        self.assertFalse(cfg.from_request_override)

    def test_applies_request_override_when_allowed(self):
        settings.adv_retrieval_enabled = False
        settings.adv_retrieval_allow_request_override = True
        settings.retrieval_strategy = "baseline"
        settings.adv_retrieval_rollout_percent = 100

        cfg = resolve_advanced_retrieval_config(
            request_payload={
                "adv_retrieval_enabled": True,
                "retrieval_strategy": "advanced_hybrid_rerank",
                "reranker_variant": "cross_encoder",
                "query_rewrite_policy": "llm",
            },
            request_id="rid-3",
        )

        self.assertTrue(cfg.enabled)
        self.assertTrue(cfg.from_request_override)
        self.assertEqual(cfg.retrieval_strategy, "advanced_hybrid_rerank")
        self.assertEqual(cfg.reranker_variant, "cross_encoder")
        self.assertEqual(cfg.query_rewrite_policy, "llm")

    def test_rollout_percent_disables_when_zero(self):
        settings.adv_retrieval_enabled = True
        settings.adv_retrieval_rollout_percent = 0

        cfg = resolve_advanced_retrieval_config(
            request_payload={},
            request_id="rid-4",
        )

        self.assertFalse(cfg.enabled)


if __name__ == "__main__":
    unittest.main()
