import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.chat import router as chat_router
from .api.upload import router as upload_router
from .api.documents import router as document_router
from .api.chunks import router as chunks_router
from .providers.factory import get_embeddings_provider


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Validate embeddings provider
    try:
        provider = get_embeddings_provider()
        expected = int(os.getenv("EXPECTED_EMBEDDING_DIM", str(provider.dim)))
        if provider.dim != expected:
            raise ValueError(
                f"Embeddings provider dimension {provider.dim} does not match expected {expected}"
            )
    except Exception as e:
        print(f"Error initializing embeddings provider: {e}")
        raise e
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


app.include_router(chat_router)
app.include_router(upload_router)
app.include_router(document_router)
app.include_router(chunks_router)
