import os
from functools import lru_cache

from .embeddings.registry import create_embeddings_provider
from .llm.openai_llm import OpenAILLM
from .llm.ollama_local import OllamaLocal


@lru_cache(maxsize=1)
def get_embeddings_provider():
    embeddings_provider_type = os.getenv("EMBEDDINGS_PROVIDER", "hf_local")
    return create_embeddings_provider(provider=embeddings_provider_type)


def reset_embeddings_provider_cache():
    get_embeddings_provider.cache_clear()


@lru_cache(maxsize=1)
def get_llm_provider():
    llm_provider_type = (
        (os.getenv("LLM_PROVIDER", "ollama") or "ollama").strip().lower()
    )
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
