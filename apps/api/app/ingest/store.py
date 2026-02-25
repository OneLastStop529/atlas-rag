from __future__ import annotations

import uuid
from typing import List, Tuple

from app.db import SessionLocal
from app.models import Chunk, Document


def insert_document_and_chunks(
    *,
    collection_id: str,
    file_name: str,
    mime_type: str,
    chunks: List[str],
    embeddings: List[List[float]],
) -> Tuple[str, int]:
    if len(chunks) != len(embeddings):
        raise ValueError("Number of chunks and embeddings must match")

    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not set")

    doc_id = uuid.uuid4()
    with SessionLocal.begin() as session:
        session.add(
            Document(
                id=doc_id,
                collection_id=collection_id,
                file_name=file_name,
                mime_type=mime_type,
                meta={},
            )
        )
        session.add_all(
            [
                Chunk(
                    id=uuid.uuid4(),
                    document_id=doc_id,
                    chunk_index=idx,
                    content=content,
                    embedding=emb,
                    meta={},
                )
                for idx, (content, emb) in enumerate(zip(chunks, embeddings))
            ]
        )

    return str(doc_id), len(chunks)
