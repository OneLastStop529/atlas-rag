from __future__ import annotations
import time
from typing import List
from langchain.embeddings.base import Embeddings
from app.providers.embeddings.registry import (
    create_embeddings_provider,
    normalize_embeddings_provider_id,
)
from app.core.reliability import (
    dependency_timeout_seconds,
    enforce_timeout_budget,
    retry_with_backoff,
)


class EmbeddingsProvider(Embeddings):
    model_name: str
    dim: int | None

    def __init__(
        self,
        dim: int | None = None,
        provider: str = "hash",
    ):
        self.dim = dim
        self.model_name = provider
        self._impl = None

        if type(self) is not EmbeddingsProvider:
            return

        provider_id = normalize_embeddings_provider_id(provider)
        self._impl = create_embeddings_provider(provider=provider_id, dim=dim)

        self.dim = self._impl.dim
        self.model_name = self._impl.model_name

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if self._impl is None:
            raise NotImplementedError(
                "embed_documents must be implemented by EmbeddingsProvider subclasses"
            )
        started_at = time.monotonic()
        vectors = retry_with_backoff(
            lambda: self._impl.embed_documents(texts),
            operation=f"embed_documents[{self.model_name}]",
        )
        enforce_timeout_budget(
            started_at=started_at,
            timeout_seconds=dependency_timeout_seconds(),
            operation=f"embed_documents[{self.model_name}]",
        )
        return vectors

    def embed_query(self, text: str) -> List[float]:
        if self._impl is None:
            raise NotImplementedError(
                "embed_query must be implemented by EmbeddingsProvider subclasses"
            )
        started_at = time.monotonic()
        vector = retry_with_backoff(
            lambda: self._impl.embed_query(text),
            operation=f"embed_query[{self.model_name}]",
        )
        enforce_timeout_budget(
            started_at=started_at,
            timeout_seconds=dependency_timeout_seconds(),
            operation=f"embed_query[{self.model_name}]",
        )
        return vector
