import os
import uuid
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from app.ingest.chunker import ChunkConfig, chunk_text
from app.ingest.embeddings import Embedder
from app.ingest.store import insert_document_and_chunks
from app.ingest.pgvector_dim import get_db_vector_dim
from app.db import get_conn

router = APIRouter()

SUPPORTED_MIME_TYPES = {
    "text/plain": "txt",
}


async def extract_text_from_file(file: UploadFile) -> str:
    """Extract text from uploaded file based on MIME type."""
    content = await file.read()

    if file.content_type == "text/plain":
        return content.decode("utf-8")
    else:
        # For unsupported types, try to decode as text
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. Supported types: {list(SUPPORTED_MIME_TYPES.keys())}",
            )


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    collection: str = Form(default="default"),
    chunk_chars: int = Form(default=2000),
    overlap_chars: int = Form(default=200),
    embeddings: str = Form(default="hash"),
):
    """Upload and ingest a document into the vector database."""

    # Validate file type
    if file.content_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Supported types: {list(SUPPORTED_MIME_TYPES.keys())}",
        )

    # Validate embeddings provider
    if embeddings not in ["sentence-transformers", "hash"]:
        raise HTTPException(
            status_code=400,
            detail="embeddings must be either 'sentence-transformers' or 'hash'",
        )

    # Validate filename
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    try:
        # Extract text from file
        text = await extract_text_from_file(file)

        if not text.strip():
            raise HTTPException(status_code=400, detail="No text content found in file")

        # Configure chunking
        cfg = ChunkConfig(chunk_chars=chunk_chars, overlap_chars=overlap_chars)
        chunks = chunk_text(text, cfg)

        if not chunks:
            raise HTTPException(status_code=400, detail="No content chunks generated")

        # Get database vector dimension
        with get_conn() as conn:
            with conn.cursor() as cur:
                dim = get_db_vector_dim(cur)

        # Generate embeddings
        embedder = Embedder(dim=dim, provider=embeddings)
        embeddings_list = embedder.embed_batch(chunks)

        # Store document and chunks
        doc_id, num_chunks = insert_document_and_chunks(
            collection_id=collection,
            file_name=file.filename,
            mime_type=file.content_type,
            chunks=chunks,
            embeddings=embeddings_list,
        )

        return {
            "ok": True,
            "doc_id": doc_id,
            "filename": file.filename,
            "collection": collection,
            "status": "ingested",
            "chunks_count": num_chunks,
            "chunk_config": {
                "chunk_chars": chunk_chars,
                "overlap_chars": overlap_chars,
            },
            "embeddings_provider": embeddings,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
