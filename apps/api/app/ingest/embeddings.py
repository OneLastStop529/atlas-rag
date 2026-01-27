from __future__ import annotations

import hashlib
import os
from typing import List


def hash_embedding(text: str, dim: int) -> List[float]:
    """
    Deterministic fake embedding (plumbing test only).
    """
    out: List[float] = []
    seed = text.encode("utf=8")
    for i in range(dim):
        h = hashlib.blake2b(seed + i.to_bytes(2, "little"), digest_size=8).digest()
        out.append(int.from_bytes(h, "little") / (2**64))

    return out


class Embedder:
    """
    v0 embedder supporting:
    - sentence-transformers (real)
    - hash (fake, for plumbing tests)
    """

    def __init__(self, dim: int, provider: str):
        self.dim = dim
        self.provider = provider
        self._st_model = None

        if provider == "sentence-transformers":
            try:
                from sentence_transformers import SentenceTransformer
            except Exception as e:
                raise ImportError(
                    "sentence-transformers package is not installed. "
                    "Please install it to use the sentence-transformers embedder."
                ) from e
            model_name = os.getenv(
                "HF_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
            )
            self._st_model = SentenceTransformer(model_name)
            model_dim = self._st_model.get_sentence_embedding_dimension()
            if model_dim != dim:
                raise RuntimeError(
                    f"Model embedding dimension {model_dim} does not match expected dimension {dim}."
                    f"Recreate DB as vector ({model_dim}) or choose a model matching {dim}."
                )

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if self.provider == "sentence-transformers":
            assert self._st_model is not None
            vecs = self._st_model.encode(texts, normalize_embeddings=True)
            return [vec.tolist() for vec in vecs]
        elif self.provider == "hash":
            return [hash_embedding(text, self.dim) for text in texts]
        else:
            raise ValueError(f"Unknown embedder provider: {self.provider}")
