from io import BytesIO

from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from pypdf import PdfReader
from app.ingest.chunker import ChunkConfig, lc_recursive_ch_text
from app.ingest.store import insert_document_and_chunks
from app.ingest.pgvector_dim import get_db_vector_dim
from app.db import get_conn
from app.providers.embeddings.base import EmbeddingsProvider

router = APIRouter()

SUPPORTED_MIME_TYPES = {
    "text/plain": "txt",
    "application/pdf": "pdf",
    "text/markdown": "md",
}

SUPPORTED_EMBEDDINGS_PROVIDERS = {
    "sentence-transformers",
    "hash",
    "hf_local",
    "tei",
    "bge-small-zh",
    "bge-large-zh",
}


def validation_error(
    message: str, fields: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "ok": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": message,
                "fields": fields or {},
            },
        },
    )


async def extract_text_from_file(file: UploadFile) -> str:
    """Extract text from uploaded file based on MIME type."""
    content = await file.read()

    if file.content_type == "text/plain" or file.content_type == "text/markdown":
        return content.decode("utf-8")
    elif file.content_type == "application/pdf":
        reader = PdfReader(BytesIO(content))
        parts = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text:
                parts.append(text)
        return "\n\n".join(parts)
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
    chunk_chars: int = Form(default=700),
    overlap_chars: int = Form(default=100),
    embeddings: str = Form(default="sentence-transformers"),
):
    """Upload and ingest a document into the vector database."""

    # Validate file type
    if file.content_type not in SUPPORTED_MIME_TYPES:
        return validation_error(
            "Unsupported file type.",
            {
                "file": (
                    f"Unsupported file type: {file.content_type}. "
                    f"Supported types: {list(SUPPORTED_MIME_TYPES.keys())}"
                )
            },
        )

    # Validate embeddings provider
    if embeddings not in SUPPORTED_EMBEDDINGS_PROVIDERS:
        return validation_error(
            "Invalid embeddings provider.",
            {
                "embeddings": (
                    "embeddings must be one of: "
                    + ", ".join(sorted(SUPPORTED_EMBEDDINGS_PROVIDERS))
                )
            },
        )

    # Validate filename
    if not file.filename:
        return validation_error(
            "Filename is required.", {"file": "Filename is required"}
        )

    if chunk_chars <= 0:
        return validation_error(
            "Invalid chunking configuration.",
            {"chunk_chars": "chunk_chars must be greater than 0"},
        )

    if overlap_chars < 0:
        return validation_error(
            "Invalid chunking configuration.",
            {"overlap_chars": "overlap_chars must be 0 or greater"},
        )

    if overlap_chars >= chunk_chars:
        return validation_error(
            "Invalid chunking configuration.",
            {"overlap_chars": "overlap_chars must be less than chunk_chars"},
        )

    try:
        # Extract text from file
        text = await extract_text_from_file(file)

        if not text.strip():
            return validation_error(
                "No text content found in file.",
                {"file": "No text content found in file"},
            )

        # Configure chunking
        cfg = ChunkConfig(chunk_chars=chunk_chars, overlap_chars=overlap_chars)
        chunks = lc_recursive_ch_text(text, cfg)

        if not chunks:
            return validation_error(
                "No content chunks generated.",
                {"file": "No content chunks generated"},
            )

        # Get database vector dimension
        with get_conn() as conn:
            with conn.cursor() as cur:
                dim = get_db_vector_dim(cur)

        # Generate embeddings

        #
        embedder_provider = EmbeddingsProvider(dim=dim, provider=embeddings)
        embeddings_list = embedder_provider.embed_documents(chunks)

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

    except HTTPException as e:
        if e.status_code == 400:
            detail = str(e.detail)
            return validation_error(detail, {"file": detail})
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
