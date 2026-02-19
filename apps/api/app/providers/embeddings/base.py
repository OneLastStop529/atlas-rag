from __future__ import annotations
import os
import time
from typing import List
from langchain.embeddings.base import Embeddings
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

        provider = provider.strip().lower()
        if provider == "hash":
            from .hash import HashEmbeddings

            self._impl = HashEmbeddings(dim=dim or 384)
        elif provider in {"sentence-transformers", "hf_local"}:
            from .sentence_transformer import SentenceTransformerEmbeddings

            model_name = os.getenv(
                "HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
            )
            self._impl = SentenceTransformerEmbeddings(model_name=model_name)
        elif provider == "bge-large-zh":
            from .bge_large import BGELargeEmbeddings

            self._impl = BGELargeEmbeddings()
        elif provider == "bge-small-zh":
            from .bge_small import BGESmallEmbeddings

            self._impl = BGESmallEmbeddings()
        elif provider == "hf_local":
            from .hf_local import HFLocalEmbeddings

            model_name = os.getenv(
                "HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
            )
            self._impl = HFLocalEmbeddings(model_name=model_name)
        elif provider == "tei":
            from .tei import TEIEmbeddings

            self._impl = TEIEmbeddings(
                dim=dim or 384,
                model_name="TEI",
                base_url=os.getenv("TEI_BASE_URL", "http://localhost:8000"),
            )
        else:
            raise ValueError(f"Unknown embedder provider: {provider}")

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
