from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


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
