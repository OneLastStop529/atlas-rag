from __future__ import annotations

import os
from urllib.parse import urlparse

from pydantic import ValidationError

from app.config import Settings
from app.providers.embeddings.registry import (
    normalize_embeddings_provider_id,
    supported_embeddings_provider_ids,
)

_ALLOWED_LLM_PROVIDERS = {"ollama", "ollama_local", "openai"}


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _parse_positive_int(raw: str, *, name: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got: {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be > 0, got: {value}")
    return value


def validate_startup_config() -> None:
    errors: list[str] = []
    warnings: list[str] = []

    # Parse app settings eagerly so invalid typed env values fail at startup.
    try:
        Settings()
    except ValidationError as exc:
        for issue in exc.errors():
            loc = ".".join(str(part) for part in issue.get("loc", ()))
            msg = issue.get("msg", "invalid value")
            errors.append(f"{loc}: {msg}")

    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        errors.append("DATABASE_URL is required.")

    llm_provider = (os.getenv("LLM_PROVIDER", "ollama") or "ollama").strip().lower()
    if llm_provider not in _ALLOWED_LLM_PROVIDERS:
        allowed = ", ".join(sorted(_ALLOWED_LLM_PROVIDERS))
        errors.append(f"LLM_PROVIDER must be one of [{allowed}], got: {llm_provider!r}")

    if llm_provider == "openai":
        openai_base = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").strip()
        if not _is_http_url(openai_base):
            errors.append(
                f"OPENAI_BASE_URL must be a valid http(s) URL when LLM_PROVIDER=openai, got: {openai_base!r}"
            )
        if not (os.getenv("OPENAI_API_KEY") or "").strip():
            warnings.append(
                "OPENAI_API_KEY is empty; startup will continue, but OpenAI runtime calls will fail."
            )

    if llm_provider in {"ollama", "ollama_local"}:
        ollama_base = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").strip()
        if not _is_http_url(ollama_base):
            errors.append(
                f"OLLAMA_BASE_URL must be a valid http(s) URL when LLM_PROVIDER=ollama, got: {ollama_base!r}"
            )

    embeddings_provider_raw = os.getenv("EMBEDDINGS_PROVIDER", "hf_local")
    embeddings_provider = normalize_embeddings_provider_id(embeddings_provider_raw)
    supported_embeddings = set(supported_embeddings_provider_ids())
    if embeddings_provider not in supported_embeddings:
        allowed = ", ".join(sorted(supported_embeddings))
        errors.append(
            f"EMBEDDINGS_PROVIDER must be one of [{allowed}], got: {embeddings_provider_raw!r}"
        )

    expected_dim_raw = (os.getenv("EXPECTED_EMBEDDING_DIM") or "").strip()
    if expected_dim_raw:
        try:
            _parse_positive_int(expected_dim_raw, name="EXPECTED_EMBEDDING_DIM")
        except ValueError as exc:
            errors.append(str(exc))

    hash_dim_raw = (os.getenv("HASH_EMBEDDING_DIM") or "").strip()
    if hash_dim_raw:
        try:
            hash_dim = _parse_positive_int(hash_dim_raw, name="HASH_EMBEDDING_DIM")
        except ValueError as exc:
            errors.append(str(exc))
        else:
            if expected_dim_raw:
                expected_dim = int(expected_dim_raw)
                if hash_dim != expected_dim:
                    errors.append(
                        "Invalid embedding dimension config: HASH_EMBEDDING_DIM "
                        f"({hash_dim}) must match EXPECTED_EMBEDDING_DIM ({expected_dim})."
                    )

    if warnings:
        # Startup warnings are surfaced via startup failure log stream too.
        for warning in warnings:
            print(f"[startup-config-warning] {warning}")

    if errors:
        joined = "\n- ".join(errors)
        raise RuntimeError(f"Startup config validation failed:\n- {joined}")
