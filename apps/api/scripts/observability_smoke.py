from __future__ import annotations

import re
import sys
from io import BytesIO
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


def _ok(name: str) -> None:
    print(f"[PASS] {name}")


def _fail(name: str, err: Exception) -> None:
    print(f"[FAIL] {name}: {err}")
    raise err


def _assert(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def smoke_request_correlation_chat_and_upload() -> None:
    name = "request correlation via X-Request-ID"
    try:
        captured: dict[str, str] = {}

        async def fake_event_stream(payload: dict, request_id: str):
            captured["chat_request_id"] = request_id
            yield "event: done\ndata: {\"ok\": true}\n\n"

        with (
            patch("app.main.check_database", return_value=None),
            patch("app.main.check_vector_extension", return_value=None),
            patch("app.main.check_embeddings_provider", return_value=None),
            patch("app.main.get_llm_provider", return_value=object()),
            patch("app.api.chat._event_stream", side_effect=fake_event_stream),
            patch("app.api.upload.extract_text_from_file", new_callable=AsyncMock) as mock_extract_text,
            patch("app.api.upload.lc_recursive_ch_text", return_value=["hello world"]),
            patch("app.api.upload.get_conn") as mock_get_conn,
            patch("app.api.upload.get_db_vector_dim", return_value=384),
            patch("app.api.upload.EmbeddingsProvider") as mock_embeddings_provider,
            patch("app.api.upload.insert_document_and_chunks", return_value=("doc-smoke", 1)),
            TestClient(app, raise_server_exceptions=False) as client,
        ):
            mock_extract_text.return_value = "hello world"
            mock_cur = mock_get_conn.return_value.__enter__.return_value.cursor.return_value
            mock_cur.__enter__.return_value = mock_cur
            mock_embeddings_provider.return_value.embed_documents.return_value = [[0.1] * 384]

            chat_request_id = "smoke-chat-rid"
            chat_resp = client.post(
                "/api/chat",
                json={"messages": [{"role": "user", "content": "ping"}]},
                headers={"X-Request-ID": chat_request_id},
            )
            _assert(chat_resp.status_code == 200, f"chat status expected 200 got {chat_resp.status_code}")
            _assert(
                chat_resp.headers.get("x-request-id") == chat_request_id,
                "chat response did not echo request id",
            )
            _assert(
                captured.get("chat_request_id") == chat_request_id,
                "chat stream did not receive request id",
            )

            upload_request_id = "smoke-upload-rid"
            upload_resp = client.post(
                "/upload",
                files={"file": ("sample.txt", BytesIO(b"hello"), "text/plain")},
                data={
                    "collection": "default",
                    "embeddings_provider": "hash",
                    "chunk_chars": "128",
                    "overlap_chars": "16",
                },
                headers={"X-Request-ID": upload_request_id},
            )
            _assert(
                upload_resp.status_code == 200,
                f"upload status expected 200 got {upload_resp.status_code}",
            )
            _assert(
                upload_resp.headers.get("x-request-id") == upload_request_id,
                "upload response did not echo request id",
            )

        _ok(name)
    except Exception as err:
        _fail(name, err)


def smoke_metrics_exposed_for_chat_and_upload() -> None:
    name = "metrics exposure for chat and upload"
    try:
        with (
            patch("app.main.check_database", return_value=None),
            patch("app.main.check_vector_extension", return_value=None),
            patch("app.main.check_embeddings_provider", return_value=None),
            patch("app.main.get_llm_provider", return_value=object()),
            TestClient(app, raise_server_exceptions=False) as client,
        ):
            metrics_resp = client.get("/metrics")
            _assert(metrics_resp.status_code == 200, f"metrics status {metrics_resp.status_code}")
            body = metrics_resp.text

        _assert("atlas_http_requests_total" in body, "missing atlas_http_requests_total")
        _assert(
            re.search(
                r'atlas_http_requests_total\{method="POST",route="/api/chat",status="200"\}\s+[1-9]\d*',
                body,
            )
            is not None,
            "missing chat request counter",
        )
        _assert(
            re.search(
                r'atlas_http_requests_total\{method="POST",route="/upload",status="200"\}\s+[1-9]\d*',
                body,
            )
            is not None,
            "missing upload request counter",
        )
        _ok(name)
    except Exception as err:
        _fail(name, err)


def main() -> int:
    print("=== Observability Smoke ===")
    smoke_request_correlation_chat_and_upload()
    smoke_metrics_exposed_for_chat_and_upload()
    print("=== Observability Smoke Complete ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(1)
