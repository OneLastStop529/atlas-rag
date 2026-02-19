from __future__ import annotations

import os
from typing import Iterable

CANONICAL_EMBEDDINGS_PROVIDER_IDS = (
    "sentence-transformers",
    "hash",
    "hf_local",
    "tei",
    "bge-small-zh",
    "bge-large-zh",
)

EMBEDDINGS_PROVIDER_ALIASES = {
    "bge_small": "bge-small-zh",
    "bge_large": "bge-large-zh",
    "bge-small": "bge-small-zh",
    "bge-large": "bge-large-zh",
}


def normalize_embeddings_provider_id(provider: str) -> str:
    provider_id = (provider or "").strip().lower()
    provider_id = EMBEDDINGS_PROVIDER_ALIASES.get(provider_id, provider_id)
    return provider_id


def supported_embeddings_provider_ids() -> Iterable[str]:
    return CANONICAL_EMBEDDINGS_PROVIDER_IDS


def create_embeddings_provider(*, provider: str, dim: int | None = None):
    provider_id = normalize_embeddings_provider_id(provider)

    if provider_id == "hash":
        from .hash import HashEmbeddings

        default_dim = int(os.getenv("HASH_EMBEDDING_DIM", "384"))
        return HashEmbeddings(dim=dim or default_dim)

    if provider_id == "sentence-transformers":
        from .sentence_transformer import SentenceTransformerEmbeddings

        model_name = os.getenv(
            "HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        return SentenceTransformerEmbeddings(model_name=model_name)

    if provider_id == "hf_local":
        from .hf_local import HFLocalEmbeddings

        model_name = os.getenv(
            "HF_EMBEDDING_MODEL",
            os.getenv("HF_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        )
        return HFLocalEmbeddings(model_name=model_name)

    if provider_id == "tei":
        from .tei import TEIEmbeddings

        tei_dim = dim or int(os.getenv("TEI_EMBEDDING_DIM", "384"))
        tei_name = os.getenv("TEI_EMBEDDING_NAME", "tei")
        return TEIEmbeddings(
            dim=tei_dim,
            model_name=tei_name,
            base_url=os.getenv("TEI_BASE_URL", "http://localhost:8000"),
        )

    if provider_id == "bge-small-zh":
        from .bge_small import BGESmallEmbeddings

        return BGESmallEmbeddings()

    if provider_id == "bge-large-zh":
        from .bge_large import BGELargeEmbeddings

        return BGELargeEmbeddings()

    raise ValueError(f"Unknown embeddings provider: {provider}")
