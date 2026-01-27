from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


from app.db import get_conn
from app.ingest.embeddings import Embedder
from app.ingest.pgvector_dim import get_db_vector_dim


@dataclass
class RetrievedChunk:
    """Data class representing a retrieved chunk with metadata."""

    chunk_id: str
    document_id: str
    content: str
    chunk_index: int
    collection_id: Optional[str]
    similarity: float
    source: str
    meta: Dict[str, Any]
    rerank_score: Optional[float] = None


def retrieve_top_k(
    query: str,
    k: int,
    collection_id: Optional[str] = None,
    embedder_provider: str = "hash",
    # hybrid_search: bool = False,
    # rerank: bool = False,
) -> List[RetrievedChunk]:
    """
    Retrieve top k chunks for a given query.

    Args:
        query: Search query text
        k: Number of top results to return
        collection_id: Optional collection ID to filter by
        hybrid_search: Whether to use hybrid search
        rerank: Whether to apply re-ranking

    Returns:
        List of top k RetrievedChunk objects
    """
    if not query:
        return []

    with get_conn() as conn:
        with conn.cursor() as cur:
            dim = get_db_vector_dim(cur)

            embedder = Embedder(dim=dim, provider=embedder_provider)
            qvec = embedder.embed_batch([query])[0]

            # NOTE:
            # psycopg2 passes Python list as PostgreSQL array, which is not compatible with pgvector
            # Cast to ::vector so <=> works
            #
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


def build_context(
    chunks: List[RetrievedChunk],
    *,
    max_chars: int = 8000,
) -> str:
    """
    Build context string from retrieved chunks.

    Args:
        chunks: List of RetrievedChunk objects
        max_tokens: Optional maximum token limit for context
        separator: String to separate chunks

    Returns:
        Formatted context string
    """
    parts: List[str] = []
    used = 0
    for c in chunks:
        header = f"[Source: {c.source} | Chunk: {c.chunk_index}]\n"
        block = header + c.content.strip()

        if used + len(block) + 2 > max_chars:
            break
        parts.append(block)
        used += len(block) + 2
    return "\n\n".join(parts)


def to_citations(
    chunks: List[RetrievedChunk],
    include_metadata: bool = True,
    max_snippet_length: int = 200,
) -> List[Dict[str, Any]]:
    """
    Convert RetrievedChunk objects to citation dictionaries.

    Args:
        chunks: List of RetrievedChunk objects
        include_metadata: Whether to include chunk metadata
        max_snippet_length: Maximum length of content snippet

    Returns:
        List of citation dictionaries
    """
    citations: List[Dict[str, Any]] = []

    for chunk in chunks:
        # Create content snippet
        if len(chunk.content) > max_snippet_length:
            snippet = chunk.content[:max_snippet_length] + "..."
        else:
            snippet = chunk.content

        citation = {
            "chunk_id": chunk.chunk_id,
            "chunk_index": chunk.chunk_index,
            "source": chunk.source,
            "document_id": chunk.document_id,
            "content": snippet,
            "similarity": chunk.similarity,
            "snippet": snippet,
        }

        if chunk.collection_id:
            citation["collection_id"] = chunk.collection_id

        if chunk.rerank_score is not None:
            citation["rerank_score"] = chunk.rerank_score

        if include_metadata and chunk.meta:
            citation["metadata"] = chunk.meta

        citations.append(citation)

    return citations
