import unittest
from io import BytesIO
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.reliability import RetryableDependencyError
from app.main import app


class ObservabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._patchers = [
            patch("app.main.validate_startup_config", return_value=None),
            patch("app.main.check_database", return_value=None),
            patch("app.main.check_vector_extension", return_value=None),
            patch("app.main.check_embeddings_provider", return_value=None),
            patch("app.main.get_llm_provider", return_value=object()),
        ]
        for patcher in cls._patchers:
            patcher.start()

        if not any(route.path == "/__test_error" for route in app.routes):
            @app.get("/__test_error")
            def _test_error():
                raise RuntimeError("boom")

    @classmethod
    def tearDownClass(cls):
        for patcher in cls._patchers:
            patcher.stop()

    def test_request_id_is_propagated_to_chat_stream_and_response(self):
        captured: dict[str, str] = {}

        async def fake_event_stream(payload: dict, request_id: str):
            captured["request_id"] = request_id
            yield "event: done\ndata: {\"ok\": true}\n\n"

        with TestClient(app, raise_server_exceptions=False) as client:
            with patch("app.api.chat._event_stream", side_effect=fake_event_stream):
                response = client.post(
                    "/api/chat",
                    json={"messages": [{"role": "user", "content": "ping"}]},
                    headers={"X-Request-ID": "rid-chat-123"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("x-request-id"), "rid-chat-123")
        self.assertEqual(captured.get("request_id"), "rid-chat-123")

    def test_http_metrics_increment_for_success_and_failure(self):
        with TestClient(app, raise_server_exceptions=False) as client:
            health = client.get("/health")
            self.assertEqual(health.status_code, 200)

            failed = client.get("/__test_error")
            self.assertEqual(failed.status_code, 500)

            metrics = client.get("/metrics")
            self.assertEqual(metrics.status_code, 200)
            body = metrics.text

        self.assertRegex(
            body,
            r'atlas_http_requests_total\{method="GET",route="/health",status="200"\}\s+[1-9]\d*',
        )
        self.assertRegex(
            body,
            r'atlas_http_requests_total\{method="GET",route="/__test_error",status="500"\}\s+[1-9]\d*',
        )

    @patch("app.api.upload.insert_document_and_chunks")
    @patch("app.api.upload.EmbeddingsProvider")
    @patch("app.api.upload.get_db_vector_dim")
    @patch("app.api.upload.get_conn")
    @patch("app.api.upload.lc_recursive_ch_text")
    @patch("app.api.upload.extract_text_from_file", new_callable=AsyncMock)
    def test_provider_failure_metric_increments_on_upload_failure(
        self,
        mock_extract_text,
        mock_chunk_text,
        mock_get_conn,
        mock_get_dim,
        mock_embeddings_provider,
        _mock_insert,
    ):
        mock_extract_text.return_value = "hello world"
        mock_chunk_text.return_value = ["hello world"]
        mock_get_dim.return_value = 384

        mock_cur = mock_get_conn.return_value.__enter__.return_value.cursor.return_value
        mock_cur.__enter__.return_value = mock_cur

        mock_embeddings_impl = mock_embeddings_provider.return_value
        mock_embeddings_impl.embed_documents.side_effect = RetryableDependencyError(
            "embedder provider down"
        )

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/upload",
                files={"file": ("sample.txt", BytesIO(b"hello world"), "text/plain")},
                data={
                    "collection": "default",
                    "embeddings_provider": "hash",
                    "chunk_chars": "128",
                    "overlap_chars": "16",
                },
            )
            self.assertEqual(response.status_code, 503)

            metrics = client.get("/metrics")
            self.assertEqual(metrics.status_code, 200)
            body = metrics.text

        self.assertRegex(
            body,
            r'atlas_provider_failures_total\{dependency="embeddings",error_code="embeddings_unavailable"\}\s+[1-9]\d*',
        )


if __name__ == "__main__":
    unittest.main()
