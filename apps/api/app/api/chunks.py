import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Chunk as ChunkORM
from app.models import Document as DocumentORM
from app.schemas import Chunk, Document

router = APIRouter()


@router.get("/chunks")
def list_chunks(
    collection_id: str = "default",
    limit: int = 10,
    offset: int = 0,
    document_id: str | None = None,
    session: Session = Depends(get_session),
):
    """List chunks with optional filtering by document."""
    stmt = (
        select(ChunkORM, DocumentORM.created_at, DocumentORM.file_name)
        .join(DocumentORM, ChunkORM.document_id == DocumentORM.id)
        .where(DocumentORM.collection_id == collection_id)
        .order_by(ChunkORM.document_id, ChunkORM.chunk_index)
        .offset(offset)
        .limit(limit)
    )
    if document_id:
        try:
            parsed_document_id = uuid.UUID(document_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid document ID format")
        stmt = stmt.where(ChunkORM.document_id == parsed_document_id)

    rows = session.execute(stmt).all()

    return {
        "items": [
            Chunk(
                id=str(chunk.id),
                document_id=str(chunk.document_id),
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                meta=chunk.meta,
                created_at=created_at,
                file_name=file_name,
            )
            for chunk, created_at, file_name in rows
        ]
    }


@router.get("/chunks/{chunk_id}")
def get_chunk(
    chunk_id: str,
    collection_id: str = "default",
    session: Session = Depends(get_session),
) -> Chunk:
    """Get a specific chunk by ID."""
    try:
        parsed_chunk_id = uuid.UUID(chunk_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chunk ID format")

    stmt = (
        select(
            ChunkORM,
            DocumentORM.created_at,
            DocumentORM.file_name,
            DocumentORM.collection_id,
        )
        .join(DocumentORM, ChunkORM.document_id == DocumentORM.id)
        .where(
            ChunkORM.id == parsed_chunk_id, DocumentORM.collection_id == collection_id
        )
    )
    row = session.execute(stmt).first()

    if not row:
        raise HTTPException(status_code=404, detail="Chunk not found")

    chunk, created_at, file_name, resolved_collection_id = row
    return Chunk(
        id=str(chunk.id),
        document_id=str(chunk.document_id),
        chunk_index=chunk.chunk_index,
        content=chunk.content,
        meta=chunk.meta,
        created_at=created_at,
        file_name=file_name,
        collection_id=resolved_collection_id,
    )


@router.get("/documents/{document_id}/chunks")
def get_document_chunks(
    document_id: str,
    collection_id: str = "default",
    limit: int = 100,
    offset: int = 0,
    session: Session = Depends(get_session),
) -> Document:
    """Get all chunks for a specific document."""
    try:
        parsed_document_id = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")

    doc_stmt = select(DocumentORM).where(
        DocumentORM.id == parsed_document_id, DocumentORM.collection_id == collection_id
    )
    doc = session.scalars(doc_stmt).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk_stmt = (
        select(ChunkORM)
        .where(ChunkORM.document_id == parsed_document_id)
        .order_by(ChunkORM.chunk_index)
        .offset(offset)
        .limit(limit)
    )
    chunk_rows = session.scalars(chunk_stmt).all()

    return Document(
        id=document_id,
        file_name=doc.file_name,
        mime_type=doc.mime_type,
        created_at=doc.created_at,
        meta=doc.meta,
        collection_id=collection_id,
        chunks=[
            Chunk(
                id=str(chunk.id),
                document_id=document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                meta=chunk.meta,
            )
            for chunk in chunk_rows
        ],
    )
