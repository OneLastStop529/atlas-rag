import unittest
from unittest.mock import patch

from app.core.health import get_readiness_payload, run_readiness_checks
from app.core.reliability import (
    RetryableDependencyError,
    enforce_timeout_budget,
    retry_with_backoff,
)


class ReliabilityHealthTests(unittest.TestCase):
    def test_retry_with_backoff_retries_transient_errors(self):
        state = {"count": 0}

        def flaky():
            state["count"] += 1
            if state["count"] < 2:
                raise TimeoutError("temporary")
            return "ok"

        with patch("app.core.reliability.time.sleep", return_value=None):
            result = retry_with_backoff(flaky, operation="flaky-test", attempts=2)

        self.assertEqual(result, "ok")
        self.assertEqual(state["count"], 2)

    def test_retry_with_backoff_raises_after_max_attempts(self):
        def always_fail():
            raise TimeoutError("still down")

        with patch("app.core.reliability.time.sleep", return_value=None):
            with self.assertRaises(RetryableDependencyError):
                retry_with_backoff(always_fail, operation="always-fail", attempts=2)

    def test_enforce_timeout_budget_raises_when_elapsed(self):
        with self.assertRaises(TimeoutError):
            enforce_timeout_budget(
                started_at=0.0,
                timeout_seconds=0.01,
                operation="timed-op",
            )

    @patch("app.core.health.check_embeddings_provider")
    @patch("app.core.health.check_vector_extension")
    @patch("app.core.health.check_database")
    def test_readiness_degraded_when_check_fails(
        self, mock_db, mock_pgvector, mock_embeddings
    ):
        mock_db.return_value = None
        mock_pgvector.side_effect = RuntimeError("pgvector missing")
        mock_embeddings.return_value = None

        payload = run_readiness_checks()
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["checks"]["database"]["status"], "ok")
        self.assertEqual(payload["checks"]["pgvector"]["status"], "error")

    @patch("app.core.health._readiness_cache_ttl_seconds", return_value=60.0)
    @patch("app.core.health.run_readiness_checks")
    def test_readiness_uses_cache(self, mock_run_checks, _mock_ttl):
        mock_run_checks.return_value = {"status": "ok", "checks": {}}
        first = get_readiness_payload(force=True)
        second = get_readiness_payload()
        self.assertEqual(first["status"], "ok")
        self.assertEqual(second["status"], "ok")
        self.assertEqual(mock_run_checks.call_count, 1)


if __name__ == "__main__":
    unittest.main()
