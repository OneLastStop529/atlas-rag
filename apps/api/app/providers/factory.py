import os
from functools import lru_cache

from .embeddings.hf_local import HFLocalEmbeddings
from .embeddings.tei import TEIEmbeddings


@lru_cache(maxsize=1)
def get_embeddings_provider():
    provider_type = os.getenv("EMBEDDINGS_PROVIDER", "hf_local")
    if provider_type == "hf_local":
        model_name = os.getenv(
            "HF_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        return HFLocalEmbeddings(model_name)

    elif provider_type == "tei":
        base_url = os.getenv("TEI_BASE_URL", "http://localhost:8000")
        dim = int(os.getenv("TEI_EMBEDDING_DIM", "384"))
        name = os.getenv("TEI_EMBEDDING_NAME", "tei")
        return TEIEmbeddings(base_url=base_url, dim=dim, name=name)

    else:
        raise ValueError(f"Unknown embeddings provider: {provider_type}")


def reset_provider_cache():
    get_embeddings_provider.cache_clear()
