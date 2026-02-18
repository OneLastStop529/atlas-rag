from app.providers.embeddings.base import EmbeddingsProvider
import hashlib


class HashEmbeddings(EmbeddingsProvider):
    def __init__(self, dim: int):
        self.model_name = "hash"
        self.dim = dim

    def embed_documents(self, texts):
        return [self._hash_embedding(text) for text in texts]

    def embed_query(self, text):
        return self._hash_embedding(text)

    def _hash_embedding(self, text):
        out = []
        seed = text.encode("utf=8")
        dim = self.dim if self.dim is not None else 128
        for i in range(dim):
            h = hashlib.blake2b(seed + i.to_bytes(2, "little"), digest_size=8).digest()
            out.append(int.from_bytes(h, "little") / (2**64))
        return out
