from fastapi import APIRouter, HTTPException
from app.db import get_conn
import uuid


router = APIRouter()


@router.get("/chunks")
def list_chunks(
    collection_id: str = "default",
    limit: int = 10,
    offset: int = 0,
    document_id: str | None = None,
):
    """List chunks with optional filtering by document."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            if document_id:
                # Validate document_id UUID format
                try:
                    uuid.UUID(document_id)
                except ValueError:
                    raise HTTPException(
                        status_code=400, detail="Invalid document ID format"
                    )

                cur.execute(
                    """
                    SELECT c.id::text, c.document_id::text, c.chunk_index, c.content, c.meta, d.created_at,
                           d.file_name
                    FROM chunks c
                    JOIN documents d ON c.document_id = d.id
                    WHERE d.collection_id = %s AND c.document_id = %s
                    ORDER BY c.document_id, c.chunk_index
                    LIMIT %s OFFSET %s
                    """,
                    (collection_id, document_id, limit, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT c.id::text, c.document_id::text, c.chunk_index, c.content, c.meta, d.created_at,
                           d.file_name
                    FROM chunks c
                    JOIN documents d ON c.document_id = d.id
                    WHERE d.collection_id = %s
                    ORDER BY c.document_id, c.chunk_index
                    LIMIT %s OFFSET %s
                    """,
                    (collection_id, limit, offset),
                )
            rows = cur.fetchall()

    return {
        "items": [
            {
                "chunk_id": r[0],
                "document_id": r[1],
                "chunk_index": r[2],
                "content": r[3],
                "meta": r[4],
                "created_at": r[5],
                "file_name": r[6],
            }
            for r in rows
        ]
    }


@router.get("/chunks/{chunk_id}")
def get_chunk(chunk_id: str, collection_id: str = "default"):
    """Get a specific chunk by ID."""
    try:
        uuid.UUID(chunk_id)  # Validate UUID format
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chunk ID format")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id::text, c.document_id::text, c.chunk_index, c.content, c.meta, d.created_at,
                       d.file_name, d.collection_id
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE c.id = %s AND d.collection_id = %s
                """,
                (chunk_id, collection_id),
            )
            row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Chunk not found")

            return {
                "chunk_id": row[0],
                "document_id": row[1],
                "chunk_index": row[2],
                "content": row[3],
                "meta": row[4],
                "created_at": row[5],
                "file_name": row[6],
                "collection_id": row[7],
            }


@router.get("/documents/{document_id}/chunks")
def get_document_chunks(
    document_id: str, collection_id: str = "default", limit: int = 100, offset: int = 0
):
    """Get all chunks for a specific document."""
    try:
        uuid.UUID(document_id)  # Validate document ID format
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Verify document exists in the collection
            cur.execute(
                """
                SELECT d.file_name FROM documents d
                WHERE d.id = %s AND d.collection_id = %s
                """,
                (document_id, collection_id),
            )
            doc_row = cur.fetchone()

            if not doc_row:
                raise HTTPException(status_code=404, detail="Document not found")

            # Get chunks for this document
            cur.execute(
                """
                SELECT c.id::text, c.chunk_index, c.content, c.meta
                FROM chunks c
                WHERE c.document_id = %s
                ORDER BY c.chunk_index
                LIMIT %s OFFSET %s
                """,
                (document_id, limit, offset),
            )
            chunk_rows = cur.fetchall()

            return {
                "document_id": document_id,
                "file_name": doc_row[0],
                "chunks": [
                    {
                        "chunk_id": r[0],
                        "chunk_index": r[1],
                        "content": r[2],
                        "meta": r[3],
                    }
                    for r in chunk_rows
                ],
            }
