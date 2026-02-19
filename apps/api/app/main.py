import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .api.chat import router as chat_router
from .api.upload import router as upload_router
from .api.documents import router as document_router
from .api.chunks import router as chunks_router
from .core.health import (
    check_database,
    check_embeddings_provider,
    check_vector_extension,
    get_readiness_payload,
)
from .providers.factory import get_llm_provider

logger = logging.getLogger(__name__)

if not logging.getLogger().handlers:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Validate dependencies and provider wiring.
    try:
        check_database()
        check_vector_extension()
        check_embeddings_provider()
        get_llm_provider()
    except Exception:
        logger.exception("Startup dependency validation failed")
        raise
    yield
    # Shutdown: Any cleanup if necessary


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/health/live")
def liveness_check():
    return {"status": "ok"}


@app.get("/health/ready")
def readiness_check():
    payload = get_readiness_payload()
    if payload["status"] != "ok":
        return JSONResponse(status_code=503, content=payload)
    return payload


app.include_router(chat_router)
app.include_router(upload_router)
app.include_router(document_router)
app.include_router(chunks_router)
