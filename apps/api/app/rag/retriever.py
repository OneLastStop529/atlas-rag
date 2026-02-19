from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from fastapi import APIRouter
from app.rag.retrievers.factory import get_retriever
from app.rag.retrievers.types import RetrievedChunk

router = APIRouter()


@router.post("/retrieve")
def retrieve(payload: dict):
    chunks = retrieve_chunks(
        query=payload["query"],
        collection_id=payload.get("collection_id", "default"),
        k=payload.get("k", 5),
        embeddings_provider=payload.get("embeddings_provider", "hash"),
        retriever_provider=payload.get("retriever_provider"),
        use_reranking=payload.get("use_reranking", False),
    )
    return {
        "context": build_context(chunks, max_chars=4000),
        "citations": to_citations(chunks),
    }


def retrieve_chunks(
    query: str,
    k: int,
    collection_id: Optional[str] = None,
    embeddings_provider: str = "hash",
    retriever_provider: Optional[str] = None,
    use_reranking: bool = False,
    rrf_k: int = 60,
    per_query_k: Optional[int] = None,
) -> List[RetrievedChunk]:
    """
    Retrieve chunks for a given query.

    Args:
        query: Search query text
        k: Number of top results to return
        collection_id: Optional collection ID to filter by
        use_reranking: Whether to apply query reformulation + RRF re-ranking
        rrf_k: RRF constant used in reciprocal rank fusion
        per_query_k: How many results to retrieve per reformulation before fusion

    Returns:
        List of RetrievedChunk objects
    """
    if not query:
        return []

    reformulations = _simple_reformulations(query) if use_reranking else [query]
    per_query_k = per_query_k or (max(k, 10) if use_reranking else k)

    retriever = get_retriever(
        retriever_provider, embeddings_provider=embeddings_provider
    )
    results_by_query: List[List[RetrievedChunk]] = []
    for q in reformulations:
        results_by_query.append(
            retriever.retrieve(
                query=q,
                collection_id=collection_id or "default",
                k=per_query_k,
            )
        )

    if not use_reranking:
        return results_by_query[0] if results_by_query else []

    fused = _rrf_fuse(results_by_query, rrf_k=rrf_k)
    return fused[:k]


def _simple_reformulations(query: str) -> List[str]:
    cleaned = re.sub(r"[^\w\s]", " ", query)
    compact = re.sub(r"\s+", " ", cleaned).strip()
    variants = [query.strip(), query.lower().strip(), compact.lower()]
    seen: set[str] = set()
    out: List[str] = []
    for v in variants:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def get_reformulations(query: str, *, use_reranking: bool) -> List[str]:
    if not query:
        return []
    return _simple_reformulations(query) if use_reranking else [query]


def _rrf_fuse(
    results: Iterable[List[RetrievedChunk]], *, rrf_k: int = 60
) -> List[RetrievedChunk]:
    scores: Dict[str, float] = {}
    chunks: Dict[str, RetrievedChunk] = {}

    for ranked in results:
        for idx, chunk in enumerate(ranked, start=1):
            score = 1.0 / (rrf_k + idx)
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + score
            if chunk.chunk_id not in chunks:
                chunks[chunk.chunk_id] = chunk

    fused = []
    for chunk_id, score in scores.items():
        chunk = chunks[chunk_id]
        chunk.rerank_score = score
        fused.append(chunk)

    fused.sort(key=lambda c: c.rerank_score or 0.0, reverse=True)
    return fused


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
