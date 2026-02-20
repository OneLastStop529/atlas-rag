from io import BytesIO
import logging
import os
from time import perf_counter

from fastapi import APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from pypdf import PdfReader
from app.ingest.chunker import ChunkConfig, lc_recursive_ch_text
from app.ingest.store import insert_document_and_chunks
from app.ingest.pgvector_dim import get_db_vector_dim
from app.core.reliability import (
    DependencyError,
    retry_with_backoff,
)
from app.core.metrics import inc_provider_failure, observe_ingestion_throughput
from app.db import get_conn
from app.providers.embeddings.base import EmbeddingsProvider
from app.providers.embeddings.registry import (
    normalize_embeddings_provider_id,
    supported_embeddings_provider_ids,
)

router = APIRouter()
logger = logging.getLogger(__name__)

SUPPORTED_MIME_TYPES = {
    "text/plain": "txt",
    "application/pdf": "pdf",
    "text/markdown": "md",
}

SUPPORTED_EMBEDDINGS_PROVIDERS = set(supported_embeddings_provider_ids())


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


def _coerce_optional_str(value) -> str | None:
    return value if isinstance(value, str) else None


def _upload_error_code(exc: Exception, stage: str | None) -> str:
    message = str(exc).lower()
    if "embed" in message:
        return "embeddings_unavailable"
    if "timeout" in message or "statement_timeout" in message:
        return "db_timeout"
    if isinstance(exc, DependencyError):
        return "dependency_unavailable"
    if stage == "upload_ingest":
        return "upload_ingest_error"
    return "upload_pipeline_error"


def _dependency_from_error_code(error_code: str) -> str:
    if error_code == "db_timeout":
        return "db"
    if error_code == "embeddings_unavailable":
        return "embeddings"
    return "upload"


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
    embeddings_provider: str | None = Form(default=None),
):
    """Upload and ingest a document into the vector database."""
    request_started_at = perf_counter()
    stage_timings_ms: dict[str, int] = {}
    failed_stage: str | None = None

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

    resolved_embeddings_provider = normalize_embeddings_provider_id(
        _coerce_optional_str(embeddings_provider) or "sentence-transformers"
    )

    # Validate embeddings provider
    if resolved_embeddings_provider not in SUPPORTED_EMBEDDINGS_PROVIDERS:
        return validation_error(
            "Invalid embeddings provider.",
            {
                "embeddings_provider": (
                    "embeddings_provider must be one of: "
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

    log_ctx = {
        "collection_id": collection,
        "embeddings_provider": resolved_embeddings_provider,
    }

    def _stage_completed(stage: str, started_at: float) -> None:
        duration_ms = int((perf_counter() - started_at) * 1000)
        stage_timings_ms[stage] = duration_ms
        logger.info(
            "upload_stage_completed",
            extra={"stage": stage, "duration_ms": duration_ms, **log_ctx},
        )

    def _stage_failed(stage: str, started_at: float, exc: Exception) -> None:
        duration_ms = int((perf_counter() - started_at) * 1000)
        logger.exception(
            "upload_stage_failed",
            extra={
                "stage": stage,
                "duration_ms": duration_ms,
                "error_code": _upload_error_code(exc, stage),
                **log_ctx,
            },
        )

    try:
        # Extract text from file
        stage_started_at = perf_counter()
        try:
            text = await extract_text_from_file(file)
        except Exception as exc:
            failed_stage = "extract_text"
            _stage_failed("extract_text", stage_started_at, exc)
            raise
        _stage_completed("extract_text", stage_started_at)

        if not text.strip():
            return validation_error(
                "No text content found in file.",
                {"file": "No text content found in file"},
            )

        # Configure chunking
        stage_started_at = perf_counter()
        try:
            cfg = ChunkConfig(chunk_chars=chunk_chars, overlap_chars=overlap_chars)
            chunks = lc_recursive_ch_text(text, cfg)
        except Exception as exc:
            failed_stage = "chunk"
            _stage_failed("chunk", stage_started_at, exc)
            raise
        _stage_completed("chunk", stage_started_at)

        if not chunks:
            return validation_error(
                "No content chunks generated.",
                {"file": "No content chunks generated"},
            )

        # Get database vector dimension
        def _resolve_vector_dim() -> int:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    statement_timeout_ms = int(os.getenv("PG_STATEMENT_TIMEOUT_MS", "15000"))
                    cur.execute("SET LOCAL statement_timeout = %s", (statement_timeout_ms,))
                    return get_db_vector_dim(cur)

        stage_started_at = perf_counter()
        try:
            dim = retry_with_backoff(_resolve_vector_dim, operation="upload_vector_dim")
        except Exception as exc:
            failed_stage = "vector_dim"
            _stage_failed("vector_dim", stage_started_at, exc)
            raise
        _stage_completed("vector_dim", stage_started_at)

        stage_started_at = perf_counter()
        try:
            embeddings_impl = EmbeddingsProvider(
                dim=dim, provider=resolved_embeddings_provider
            )
            embeddings_list = embeddings_impl.embed_documents(chunks)

            doc_id, num_chunks = retry_with_backoff(
                lambda: insert_document_and_chunks(
                    collection_id=collection,
                    file_name=file.filename,
                    mime_type=file.content_type,
                    chunks=chunks,
                    embeddings=embeddings_list,
                ),
                operation="upload_insert_chunks",
            )
        except Exception as exc:
            failed_stage = "upload_ingest"
            _stage_failed("upload_ingest", stage_started_at, exc)
            raise
        _stage_completed("upload_ingest", stage_started_at)

        payload = {
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
            "embeddings_provider": resolved_embeddings_provider,
        }
        logger.info(
            "upload_ingested",
            extra={
                "collection_id": collection,
                "embeddings_provider": resolved_embeddings_provider,
                "chunk_count": num_chunks,
            },
        )
        logger.info(
            "upload_pipeline_summary",
            extra={
                "status": "ok",
                "stages_ms": stage_timings_ms,
                "total_latency_ms": int((perf_counter() - request_started_at) * 1000),
                "chunk_count": num_chunks,
                **log_ctx,
            },
        )
        observe_ingestion_throughput(files=1, chunks=num_chunks)
        return payload

    except HTTPException as e:
        if e.status_code == 400:
            detail = str(e.detail)
            return validation_error(detail, {"file": detail})
        raise
    except DependencyError as e:
        error_code = _upload_error_code(e, failed_stage)
        inc_provider_failure(
            dependency=_dependency_from_error_code(error_code),
            error_code=error_code,
        )
        logger.error(
            "upload_dependency_failure",
            extra={
                "stage": failed_stage or "unknown",
                "error_code": error_code,
                "error": str(e),
                **log_ctx,
            },
        )
        logger.info(
            "upload_pipeline_summary",
            extra={
                "status": "error",
                "failed_stage": failed_stage or "unknown",
                "error_code": error_code,
                "stages_ms": stage_timings_ms,
                "total_latency_ms": int((perf_counter() - request_started_at) * 1000),
                **log_ctx,
            },
        )
        raise HTTPException(
            status_code=503,
            detail=f"Dependency unavailable (retryable={e.retryable}): {e}",
        )
    except Exception as e:
        error_code = _upload_error_code(e, failed_stage)
        inc_provider_failure(
            dependency=_dependency_from_error_code(error_code),
            error_code=error_code,
        )
        logger.error(
            "upload_dependency_failure",
            extra={
                "stage": failed_stage or "unknown",
                "error_code": error_code,
                "error": str(e),
                **log_ctx,
            },
        )
        logger.info(
            "upload_pipeline_summary",
            extra={
                "status": "error",
                "failed_stage": failed_stage or "unknown",
                "error_code": error_code,
                "stages_ms": stage_timings_ms,
                "total_latency_ms": int((perf_counter() - request_started_at) * 1000),
                **log_ctx,
            },
        )
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
