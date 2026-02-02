import os
from functools import lru_cache

from .embeddings.hf_local import HFLocalEmbeddings
from .embeddings.tei import TEIEmbeddings
from .llm.openai_llm import OpenAILLM
from .llm.ollama_local import OllamaLocal


@lru_cache(maxsize=1)
def get_embeddings_provider():
    embeddings_provider_type = os.getenv("EMBEDDINGS_PROVIDER", "hf_local")
    if embeddings_provider_type == "hf_local":
        model_name = os.getenv(
            "HF_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        return HFLocalEmbeddings(model_name)

    elif embeddings_provider_type == "tei":
        base_url = os.getenv("TEI_BASE_URL", "http://localhost:8000")
        dim = int(os.getenv("TEI_EMBEDDING_DIM", "384"))
        name = os.getenv("TEI_EMBEDDING_NAME", "tei")
        return TEIEmbeddings(base_url=base_url, dim=dim, name=name)

    else:
        raise ValueError(f"Unknown embeddings provider: {embeddings_provider_type}")


def reset_embeddings_provider_cache():
    get_embeddings_provider.cache_clear()


@lru_cache(maxsize=1)
def get_llm_provider():
    llm_provider_type = (os.getenv("LLM_PROVIDER", "ollama") or "ollama").strip().lower()
    if llm_provider_type == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        base_url = os.getenv("OPENAI_BASE_URL")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return OpenAILLM(api_key=api_key, model=model, base_url=base_url)

    elif llm_provider_type in {"ollama", "ollama_local"}:
        model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        base_url = os.getenv("OLLAMA_BASE_URL")
        return OllamaLocal(model=model, base_url=base_url)
    else:
        raise ValueError(f"Unknown LLM provider: {llm_provider_type}")


def reset_llm_provider_cache():
    get_llm_provider.cache_clear()
