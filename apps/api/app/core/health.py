from __future__ import annotations

import os
import time
from typing import Any

from sqlalchemy import text

from app.db import session_scope
from app.providers.factory import get_embeddings_provider


_readiness_cache: dict[str, Any] = {"ts": 0.0, "payload": None}


def _readiness_cache_ttl_seconds() -> float:
    raw = os.getenv("READINESS_CACHE_TTL_SECONDS", "5")
    try:
        value = float(raw)
    except ValueError:
        return 5.0
    return max(0.0, value)


def check_database() -> None:
    with session_scope() as session:
        session.execute(text("SELECT 1")).scalar_one()


def check_vector_extension() -> None:
    with session_scope() as session:
        row = session.execute(
            text("SELECT 1 FROM pg_extension WHERE extname='vector'")
        ).first()
        if not row:
            raise RuntimeError("pgvector extension is not installed")


def check_embeddings_provider() -> None:
    provider = get_embeddings_provider()
    if provider.dim is None or provider.dim <= 0:
        raise RuntimeError("Embeddings provider has invalid dimension")
    expected = os.getenv("EXPECTED_EMBEDDING_DIM")
    if expected:
        expected_dim = int(expected)
        if provider.dim != expected_dim:
            raise RuntimeError(
                f"Embeddings provider dimension {provider.dim} does not match expected {expected_dim}"
            )


def run_readiness_checks() -> dict[str, Any]:
    checks: dict[str, dict[str, str]] = {}

    for name, check_fn in (
        ("database", check_database),
        ("pgvector", check_vector_extension),
        ("embeddings_provider", check_embeddings_provider),
    ):
        try:
            check_fn()
            checks[name] = {"status": "ok"}
        except Exception as exc:
            checks[name] = {"status": "error", "message": str(exc)}

    ok = all(item["status"] == "ok" for item in checks.values())
    return {"status": "ok" if ok else "degraded", "checks": checks}


def get_readiness_payload(force: bool = False) -> dict[str, Any]:
    now = time.monotonic()
    ttl = _readiness_cache_ttl_seconds()
    payload = _readiness_cache["payload"]
    ts = _readiness_cache["ts"]

    if not force and payload and (now - ts) < ttl:
        return payload

    payload = run_readiness_checks()
    _readiness_cache["ts"] = now
    _readiness_cache["payload"] = payload
    return payload
