import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_session
from app.models import Document as DocumentORM
from app.schemas import Chunk, Document


router = APIRouter()


@router.get("/documents")
def list_documents(
    collection_id: str = "default",
    limit: int = 10,
    offset: int = 0,
    session: Session = Depends(get_session),
):
    stmt = (
        select(DocumentORM)
        .where(DocumentORM.collection_id == collection_id)
        .order_by(DocumentORM.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = session.scalars(stmt).all()

    return {
        "items": [
            Document(
                id=str(r.id),
                file_name=r.file_name,
                mime_type=r.mime_type,
                created_at=r.created_at,
                collection_id=r.collection_id,
                meta=None,  # Meta is not included in the list view
            )
            for r in rows
        ]
    }


@router.get("/documents/{document_id}")
def get_document(
    document_id: str,
    collection_id: str = "default",
    session: Session = Depends(get_session),
) -> Document:
    try:
        parsed_document_id = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")

    stmt = (
        select(DocumentORM)
        .options(selectinload(DocumentORM.chunks))
        .where(
            DocumentORM.id == parsed_document_id,
            DocumentORM.collection_id == collection_id,
        )
    )
    doc = session.scalars(stmt).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return Document(
        id=str(doc.id),
        file_name=doc.file_name,
        mime_type=doc.mime_type,
        created_at=doc.created_at,
        meta=doc.meta,
        collection_id=doc.collection_id,
        chunks=[
            Chunk(
                id=str(chunk.id),
                document_id=str(chunk.document_id),
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                meta=chunk.meta,
            )
            for chunk in doc.chunks
        ],
    )


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: str,
    collection_id: str = "default",
    session: Session = Depends(get_session),
):
    try:
        parsed_document_id = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format")

    stmt = select(DocumentORM).where(
        DocumentORM.id == parsed_document_id,
        DocumentORM.collection_id == collection_id,
    )
    doc = session.scalars(stmt).first()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_name = doc.file_name
    session.delete(doc)
    session.commit()

    return {
        "message": f"Document '{file_name}' deleted successfully",
        "document_id": document_id,
    }
