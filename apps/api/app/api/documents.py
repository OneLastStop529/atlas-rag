from fastapi import APIRouter, HTTPException
from app.db import get_conn
import uuid


router = APIRouter()


@router.get("/documents")
def list_documents(collection_id: str = "default", limit: int = 10, offset: int = 0):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.id::text, d.file_name, d.mime_type, d.created_at,
                (SELECT COUNT(*) FROM chunks c WHERE c.document_id = d.id) AS chunk_count
                FROM documents d
                WHERE d.collection_id = %s
                ORDER BY d.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (collection_id, limit, offset),
            )
            rows = cur.fetchall()

    return {
        "items": [
            {
                "document_id": r[0],
                "file_name": r[1],
                "mime_type": r[2],
                "created_at": r[3],
                "chunk_count": r[4],
            }
            for r in rows
        ]
    }


@router.get("/documents/{document_id}")
def get_document(document_id: str, collection_id: str = "default"):
    try:
        uuid.UUID(document_id)  # Validate UUID format
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Get document info
            cur.execute(
                """
                SELECT d.id::text, d.file_name, d.mime_type, d.created_at, d.meta
                FROM documents d
                WHERE d.id = %s AND d.collection_id = %s
                """,
                (document_id, collection_id),
            )
            doc_row = cur.fetchone()

            if not doc_row:
                raise HTTPException(status_code=404, detail="Document not found")

            # Get document chunks
            cur.execute(
                """
                SELECT chunk_index, content, meta
                FROM chunks
                WHERE document_id = %s
                ORDER BY chunk_index
                """,
                (document_id,),
            )
            chunk_rows = cur.fetchall()

            return {
                "document_id": doc_row[0],
                "file_name": doc_row[1],
                "mime_type": doc_row[2],
                "created_at": doc_row[3],
                "meta": doc_row[4],
                "chunks": [
                    {
                        "chunk_index": r[0],
                        "content": r[1],
                        "meta": r[2],
                    }
                    for r in chunk_rows
                ],
            }


@router.delete("/documents/{document_id}")
def delete_document(document_id: str, collection_id: str = "default"):
    try:
        uuid.UUID(document_id)  # Validate UUID format
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Check if document exists and get info
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

            # Delete document (chunks will be deleted due to CASCADE)
            cur.execute(
                "DELETE FROM documents WHERE id = %s AND collection_id = %s",
                (document_id, collection_id),
            )

            conn.commit()

            return {
                "message": f"Document '{doc_row[0]}' deleted successfully",
                "document_id": document_id,
            }
