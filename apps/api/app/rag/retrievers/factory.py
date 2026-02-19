from __future__ import annotations

import os

from .top_k import TopKRetriever


def get_retriever(name: str | None, *, embeddings_provider: str):
    retriever_name = (name or os.getenv("RETRIEVER_PROVIDER", "top_k")).strip().lower()
    if retriever_name == "top_k":
        return TopKRetriever(embeddings_provider=embeddings_provider)
    raise ValueError(f"Unknown retriever provider: {retriever_name}")
