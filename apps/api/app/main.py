import logging
from time import perf_counter
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
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
from .core.observability import (
    configure_logging,
    generate_request_id,
    reset_request_id,
    set_request_id,
)
from .core.metrics import observe_http_request, render_prometheus_text
from .providers.factory import get_llm_provider

logger = logging.getLogger(__name__)

configure_logging()


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


@app.middleware("http")
async def request_observability_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or generate_request_id()
    token = set_request_id(request_id)
    start = perf_counter()
    path = request.url.path

    try:
        response = await call_next(request)
    except Exception:
        latency_ms = int((perf_counter() - start) * 1000)
        observe_http_request(
            route=path,
            method=request.method,
            status_code=500,
            latency_ms=latency_ms,
        )
        logger.exception(
            "request_failed",
            extra={
                "route": path,
                "method": request.method,
                "status_code": 500,
                "latency_ms": latency_ms,
            },
        )
        raise
    else:
        response.headers["X-Request-ID"] = request_id
        latency_ms = int((perf_counter() - start) * 1000)
        observe_http_request(
            route=path,
            method=request.method,
            status_code=response.status_code,
            latency_ms=latency_ms,
        )
        logger.info(
            "request_completed",
            extra={
                "route": path,
                "method": request.method,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
            },
        )
        return response
    finally:
        # Keep request-scoped context bounded to a single request.
        reset_request_id(token)


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


@app.get("/metrics")
def metrics():
    return Response(
        content=render_prometheus_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


app.include_router(chat_router)
app.include_router(upload_router)
app.include_router(document_router)
app.include_router(chunks_router)
