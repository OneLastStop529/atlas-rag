from __future__ import annotations

import uuid
from typing import List, Tuple

from psycopg2.extras import Json

from app.db import get_conn


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

    doc_id = str(uuid.uuid4())

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (id, collection_id, file_name, mime_type)
                VALUES (%s, %s, %s, %s)
                """,
                (doc_id, collection_id, file_name, mime_type),
            )

            for idx, (content, emb) in enumerate(zip(chunks, embeddings)):
                chunk_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO chunks (id, document_id, chunk_index, content, embedding, meta)
                    VALUES (%s, %s, %s, %s, %s::vector, %s)
                    """,
                    (chunk_id, doc_id, idx, content, emb, Json({})),
                )
        conn.commit()
    return str(doc_id), len(chunks)
