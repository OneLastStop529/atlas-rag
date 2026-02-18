from sentence_transformers import SentenceTransformer
from .base import EmbeddingsProvider


class HFLocalEmbeddings(EmbeddingsProvider):
    def __init__(self, model_name: str):
        self.model_name = f"hf_local_{model_name}"
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()

    def embed_documents(self, texts):
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text):
        return self.model.encode([text], normalize_embeddigns=True)[0].tolist()
