import torch
from transformers import AutoModel, AutoTokenizer

from .base import EmbeddingsProvider


class BGELargeEmbeddings(EmbeddingsProvider):
    def __init__(self):
        self.dim = 1024
        self.model_name = "BAAI/bge-large-zh"

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

    def rrf_fusion(self, query, candidates, bm25_scores, top_k=5):
        query_vec = self.embed_query(query)
        candidate_vecs = self.embed_documents(candidates)

        # Compute cosine similarity
        query_tensor = torch.tensor(query_vec).unsqueeze(0)  # Shape: (1, dim)
        candidate_tensors = torch.tensor(candidate_vecs)  # Shape: (num_candidates, dim)

        cosine_similarities = torch.nn.functional.cosine_similarity(
            query_tensor, candidate_tensors
        ).tolist()

        # RRF fusion
        fused_scores = []
        for i in range(len(candidates)):
            bm25_score = bm25_scores[i]
            cosine_score = cosine_similarities[i]
            fused_score = 1 / (bm25_score + 1) + 1 / (cosine_score + 1)
            fused_scores.append((fused_score, candidates[i]))

        fused_scores.sort(key=lambda x: x[0], reverse=True)
        return [candidate for _, candidate in fused_scores[:top_k]]

    # Simple hybrid search that combines cosine similarity of embeddings with BM25 scores.
    def hybrid_search(self, query, candidates, top_k=5):
        query_vec = self.embed_query(query)
        candidate_vecs = self.embed_documents(candidates)

        # Compute cosine similarity
        query_tensor = torch.tensor(query_vec).unsqueeze(0)  # Shape: (1, dim)
        candidate_tensors = torch.tensor(candidate_vecs)  # Shape: (num_candidates, dim)

        cosine_similarities = torch.nn.functional.cosine_similarity(
            query_tensor, candidate_tensors
        )
        top_k_indices = torch.topk(cosine_similarities, k=top_k).indices.tolist()
        return [candidates[i] for i in top_k_indices]
