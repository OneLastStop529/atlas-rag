from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    id: str | None = None
    document_id: str | None = None
    chunk_index: int
    content: str
    meta: dict[str, Any] | None = None
    created_at: datetime | None = None
    file_name: str | None = None
    collection_id: str | None = None


class Document(BaseModel):
    id: str
    file_name: str
    mime_type: str | None = None
    created_at: datetime | None = None
    meta: dict[str, Any] | None = None
    collection_id: str = "default"
    chunks: list[Chunk] = Field(default_factory=list)
