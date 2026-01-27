from __future__ import annotations
from typing import Protocol, List


class EmbeddingsProvider(Protocol):
    name: str
    dim: int | None

    def embed_texts(self, texts: List[str]) -> List[List[float]]: ...
    def embed_quety(self, text: str) -> List[float]: ...
