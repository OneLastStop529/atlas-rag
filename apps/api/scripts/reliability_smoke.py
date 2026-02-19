from __future__ import annotations

import asyncio
import json
import sys
from unittest.mock import AsyncMock, patch

from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, UploadFile
from io import BytesIO

from app.api.chat import _event_stream
from app.api.upload import upload_document
from app.core.reliability import RetryableDependencyError, retry_with_backoff
from app.main import app, health_check, liveness_check, readiness_check


def _ok(name: str) -> None:
    print(f"[PASS] {name}")


def _fail(name: str, err: Exception) -> None:
    print(f"[FAIL] {name}: {err}")
    raise err


def _assert(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def smoke_health_endpoints() -> None:
    name = "health endpoints"
    try:
        live = liveness_check()
        health = health_check()
        _assert(live.get("status") == "ok", f"/health/live payload invalid: {live}")
        _assert(health.get("status") == "ok", f"/health payload invalid: {health}")

        with patch("app.main.get_readiness_payload", return_value={"status": "ok", "checks": {}}):
            ready_ok = readiness_check()
            _assert(isinstance(ready_ok, dict), f"expected dict readiness payload, got {type(ready_ok)}")
            _assert(ready_ok.get("status") == "ok", f"unexpected readiness payload: {ready_ok}")
        with patch(
            "app.main.get_readiness_payload",
            return_value={"status": "degraded", "checks": {"database": {"status": "error"}}},
        ):
            ready_bad = readiness_check()
            _assert(isinstance(ready_bad, JSONResponse), "expected JSONResponse for degraded readiness")
            _assert(ready_bad.status_code == 503, f"expected 503, got {ready_bad.status_code}")
        _ok(name)
    except Exception as err:
        _fail(name, err)


def smoke_startup_fail_fast() -> None:
    name = "startup fail-fast"
    try:
        async def _runner():
            with patch("app.main.check_database", side_effect=RuntimeError("db down")):
                try:
                    async with app.router.lifespan_context(app):
                        pass
                except RuntimeError:
                    return
                raise AssertionError("startup should fail when dependency checks fail")

        asyncio.run(_runner())
        _ok(name)
    except Exception as err:
        _fail(name, err)


class _FakeLLM:
    def latest_user_text(self, messages):
        return "hello"

    def build_llm_messages(self, *, query: str, context: str):
        return [{"role": "user", "content": query}, {"role": "system", "content": context}]

    async def stream_chat(self, messages):
        yield {"delta": "ok"}


async def _collect_chat_events(payload: dict) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    async for chunk in _event_stream(payload):
        lines = [line for line in chunk.splitlines() if line]
        event = lines[0].split("event: ", 1)[1]
        data = json.loads(lines[1].split("data: ", 1)[1])
        out.append((event, data))
    return out


def smoke_chat_dependency_error_sse() -> None:
    name = "chat SSE dependency error mapping"
    try:
        payload = {"messages": [{"role": "user", "content": "ping"}]}
        with patch("app.api.chat._select_llm", return_value=_FakeLLM()):
            with patch(
                "app.api.chat._retrieve_chunks",
                side_effect=RetryableDependencyError("db unavailable"),
            ):
                events = asyncio.run(_collect_chat_events(payload))
        error_events = [data for event, data in events if event == "error"]
        _assert(error_events, "expected SSE error event")
        err = error_events[0]
        _assert(err.get("code") == "DEPENDENCY_ERROR", "expected DEPENDENCY_ERROR code")
        _assert(err.get("retryable") is True, "expected retryable=true")
        _ok(name)
    except Exception as err:
        _fail(name, err)


def _make_upload_file(content: bytes) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename="sample.txt",
        headers=Headers({"content-type": "text/plain"}),
    )


def smoke_upload_dependency_503() -> None:
    name = "upload dependency maps to 503"
    try:
        with patch("app.api.upload.extract_text_from_file", new_callable=AsyncMock) as mock_extract:
            with patch("app.api.upload.lc_recursive_ch_text", return_value=["chunk"]):
                with patch("app.api.upload.get_conn") as mock_get_conn:
                    with patch("app.api.upload.get_db_vector_dim", return_value=384):
                        with patch("app.api.upload.EmbeddingsProvider") as mock_provider:
                            mock_extract.return_value = "hello"
                            mock_cur = mock_get_conn.return_value.__enter__.return_value.cursor.return_value
                            mock_cur.__enter__.return_value = mock_cur
                            mock_provider.return_value.embed_documents.side_effect = RetryableDependencyError(
                                "provider down"
                            )
                            try:
                                asyncio.run(
                                    upload_document(
                                        file=_make_upload_file(b"hello"),
                                        embeddings_provider="hash",
                                        chunk_chars=128,
                                        overlap_chars=16,
                                    )
                                )
                            except Exception as err:
                                from fastapi import HTTPException

                                _assert(isinstance(err, HTTPException), "expected HTTPException")
                                _assert(err.status_code == 503, f"expected 503 got {err.status_code}")
                                _ok(name)
                                return
        raise AssertionError("expected upload_document to raise HTTPException(503)")
    except Exception as err:
        _fail(name, err)


def smoke_retry_behavior() -> None:
    name = "retry behavior bounded"
    try:
        state = {"count": 0}

        def flaky():
            state["count"] += 1
            if state["count"] < 2:
                raise TimeoutError("temporary")
            return "ok"

        with patch("app.core.reliability.time.sleep", return_value=None):
            got = retry_with_backoff(flaky, operation="flaky", attempts=2)
            _assert(got == "ok", "expected retry to succeed on second attempt")

            def always_fail():
                raise TimeoutError("down")

            try:
                retry_with_backoff(always_fail, operation="always-fail", attempts=2)
            except RetryableDependencyError:
                _ok(name)
                return
        raise AssertionError("expected bounded retry to raise after max attempts")
    except Exception as err:
        _fail(name, err)


def main() -> int:
    print("=== Reliability Smoke ===")
    smoke_health_endpoints()
    smoke_startup_fail_fast()
    smoke_chat_dependency_error_sse()
    smoke_upload_dependency_503()
    smoke_retry_behavior()
    print("=== Reliability Smoke Complete ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(1)
