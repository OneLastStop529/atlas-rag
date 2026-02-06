from __future__ import annotations

import os

from .top_k import TopKRetriever


def get_retriever(name: str | None, *, embedder_provider: str):
    retriever_name = (name or os.getenv("RETRIEVER_PROVIDER", "top_k")).strip().lower()
    if retriever_name == "top_k":
        return TopKRetriever(embedder_provider=embedder_provider)
    raise ValueError(f"Unknown retriever provider: {retriever_name}")
