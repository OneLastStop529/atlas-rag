import torch
from transformers import AutoModel, AutoTokenizer

from .base import EmbeddingsProvider


class BGESmallEmbeddings(EmbeddingsProvider):
    def __init__(self):
        self.dim = 384
        self.model_name = "BAAI/bge-small-zh"

    def get_model_name(self):
        return self.model_name

    def embed_documents(self, texts):
        tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        model = AutoModel.from_pretrained(self.model_name)

        inputs = tokenizer(texts, padding=True, truncation=True, return_tensors="pt")
        with torch.no_grad():
            outputs = model(**inputs)
            embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
        return embeddings.tolist()

    def embed_query(self, text):
        return self.embed_documents([text])[0]
