import httpx
import os
from .base import EmbeddingsProvider


class TEIEmbeddings(EmbeddingsProvider):
    def __init__(self, base_url: str, dim: int, model_name: str = "tei"):
        self.base_url = base_url.rstrip("/")
        self.dim = dim
        self.model_name = model_name

    def embed_documents(self, texts):
        timeout = float(os.getenv("EMBEDDINGS_HTTP_TIMEOUT_SECONDS", "30"))
        response = httpx.post(
            f"{self.base_url}/embed",
            json={"inputs": texts},
            timeout=timeout,
        )
        response.raise_for_status()
        vecs = response.json()
        return vecs

    def embed_query(self, text):
        return self.embed_documents([text])[0]
