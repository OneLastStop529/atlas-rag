import httpx
from .base import EmbeddingsProvider


class TEIEmbeddings(EmbeddingsProvider):
    def __init__(self, base_url: str, dim: int, name: str = "tei"):
        self.base_url = base_url.rstrip("/")
        self.dim = dim
        self.name = name

    def embed_texts(self, texts):
        response = httpx.post(
            f"{self.base_url}/embed",
            json={"inputs": texts},
            timeout=60,
        )
        response.raise_for_status()
        vecs = response.json()
        return vecs

    def embed_quety(self, text):
        return self.embed_texts([text])[0]
