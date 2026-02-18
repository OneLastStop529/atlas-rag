from sentence_transformers import SentenceTransformer
from .base import EmbeddingsProvider


class SentenceTransformerEmbeddings(EmbeddingsProvider):
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def get_model_name(self):
        return self.model_name

    def embed_documents(self, texts):
        vecs = self.model.encode(texts, normalize_embeddings=True)
        return [vec.tolist() for vec in vecs]

    def embed_query(self, text):
        return self.embed_documents([text])[0]
