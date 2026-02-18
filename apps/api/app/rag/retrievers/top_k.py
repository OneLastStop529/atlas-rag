from __future__ import annotations

from typing import List

from app.db import get_conn
from app.ingest.pgvector_dim import get_db_vector_dim
from app.providers.embeddings.base import EmbeddingsProvider

from .types import RetrievedChunk


class TopKRetriever:
    name = "top_k"

    def __init__(self, *, embedder_provider: str = "hash") -> None:
        self.embedder_provider = embedder_provider

    def retrieve(
        self, *, query: str, collection_id: str, k: int
    ) -> List[RetrievedChunk]:
        if not query:
            return []

        with get_conn() as conn:
            with conn.cursor() as cur:
                dim = get_db_vector_dim(cur)
                embedder = EmbeddingsProvider(dim=dim, provider=self.embedder_provider)
                qvec = embedder.embed_query(query)
                cur.execute(
                    """
                    SELECT
                        c.id::text as chunk_id,
                        c.document_id::text as document_id,
                        c.chunk_index,
                        c.content,
                        (c.embedding <=> %s::vector) AS similarity,
                        d.file_name,
                        c.meta
                    FROM chunks c
                    JOIN documents d ON c.document_id = d.id
                    WHERE (%s IS NULL OR d.collection_id = %s)
                    ORDER BY c.embedding <=> (%s)::vector
                    LIMIT %s
                    """,
                    (qvec, collection_id, collection_id, qvec, k),
                )
                rows = cur.fetchall()

        out: List[RetrievedChunk] = []
        for (
            chunk_id,
            document_id,
            chunk_index,
            content,
            similarity,
            source,
            meta,
        ) in rows:
            out.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    content=content,
                    chunk_index=chunk_index,
                    collection_id=None,
                    source=source,
                    similarity=similarity,
                    meta=meta if meta else {},
                )
            )
        return out
