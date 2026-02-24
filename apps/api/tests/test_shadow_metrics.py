import re
import unittest

from app.core.metrics import observe_retrieval_shadow_eval, render_prometheus_text


class ShadowMetricsTests(unittest.TestCase):
    def test_shadow_eval_metrics_are_exposed(self):
        observe_retrieval_shadow_eval(
            status="ok",
            primary_strategy="baseline_test",
            shadow_strategy="advanced_hybrid_test",
            jaccard=0.62,
            latency_delta_ms=120,
            context_token_delta=45,
            top1_source_same=True,
        )

        metrics = render_prometheus_text()

        self.assertRegex(
            metrics,
            r'atlas_retrieval_shadow_eval_total\{primary_strategy="baseline_test",shadow_strategy="advanced_hybrid_test",status="ok"\}\s+[1-9]\d*',
        )
        self.assertRegex(
            metrics,
            r'atlas_retrieval_shadow_top1_agreement_total\{match="true"\}\s+[1-9]\d*',
        )
        self.assertTrue(
            re.search(
                r'atlas_retrieval_shadow_jaccard_sum\{primary_strategy="baseline_test",shadow_strategy="advanced_hybrid_test",status="ok"\}\s+',
                metrics,
            )
        )
        self.assertTrue(
            re.search(
                r'atlas_retrieval_shadow_latency_delta_ms_bucket\{le="250.0",primary_strategy="baseline_test",shadow_strategy="advanced_hybrid_test",status="ok"\}\s+',
                metrics,
            )
        )
        self.assertTrue(
            re.search(
                r'atlas_retrieval_shadow_context_token_delta_bucket\{le="50.0",primary_strategy="baseline_test",shadow_strategy="advanced_hybrid_test",status="ok"\}\s+',
                metrics,
            )
        )


if __name__ == "__main__":
    unittest.main()
