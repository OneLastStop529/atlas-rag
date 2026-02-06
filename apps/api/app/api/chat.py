import json
import logging
import os
from typing import Any, AsyncGenerator, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Literal

from app.providers.factory import get_llm_provider
from app.providers.llm.openai_llm import OpenAILLM
from app.providers.llm.ollama_local import OllamaLocal
from app.rag.retriever import build_context, retrieve_chunks, to_citations, get_reformulations


logger = logging.getLogger(__name__)
router = APIRouter()


def sse(event: str, data: dict) -> str:
    """Format data as Server-Sent Events (SSE)."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    collection_id: str = "default"
    messages: List[ChatMessage] = Field(default_factory=list)
    k: int = Field(default=5, ge=1, le=50)
    embedder_provider: str = "hash"
    retriever_provider: Optional[str] = None
    use_reranking: bool = False
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_base_url: Optional[str] = None


def _build_llm_provider(provider: str | None, model: str | None, base_url: str | None):
    provider_name = (provider or os.getenv("LLM_PROVIDER", "ollama")).strip().lower()
    if provider_name == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=400, detail="OPENAI_API_KEY is required for OpenAI tests."
            )
        model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        base_url = base_url or os.getenv("OPENAI_BASE_URL")
        return OpenAILLM(api_key=api_key, model=model, base_url=base_url)

    if provider_name in {"ollama", "ollama_local"}:
        model = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        base_url = base_url or os.getenv("OLLAMA_BASE_URL")
        return OllamaLocal(model=model, base_url=base_url)

    raise HTTPException(
        status_code=400, detail=f"Unknown LLM provider: {provider_name}"
    )


def _select_llm(params: ChatRequest) -> Any:
    if params.llm_provider or params.llm_model or params.llm_base_url:
        return _build_llm_provider(
            params.llm_provider, params.llm_model, params.llm_base_url
        )
    return get_llm_provider()


def _extract_query(llm: Any, params: ChatRequest) -> str:
    return llm.latest_user_text([m.model_dump() for m in params.messages])


def _retrieve_chunks(params: ChatRequest, query: str):
    return retrieve_chunks(
        query=query,
        collection_id=params.collection_id,
        k=params.k,
        embedder_provider=params.embedder_provider,
        retriever_provider=params.retriever_provider,
        use_reranking=params.use_reranking,
    )


async def _stream_llm_answer(
    *, llm, query: str, context: str
) -> AsyncGenerator[str, None]:
    llm_messages = llm.build_llm_messages(query=query, context=context)
    async for chunk in llm.stream_chat(llm_messages):
        delta = chunk.get("delta")
        if delta:
            yield sse("token", {"delta": delta})


async def _event_stream(payload: dict) -> AsyncGenerator[str, None]:
    try:
        params = ChatRequest.model_validate(payload)
        llm = _select_llm(params)
        query = _extract_query(llm, params)

        if not query:
            yield sse("error", {"message": "No user query found in messages"})
            yield sse("done", {})
            return

        logger.debug("chat_params", extra={"params": params.model_dump()})

        if params.use_reranking:
            reformulations = get_reformulations(
                query, use_reranking=params.use_reranking
            )
            yield sse("reformulations", {"items": reformulations})

        chunks = _retrieve_chunks(params, query)
        logger.info(
            "retrieval_count",
            extra={
                "count": len(chunks),
                "collection_id": params.collection_id,
            },
        )
        context = build_context(chunks, max_chars=4000)
        citations = to_citations(chunks)

        async for chunk in _stream_llm_answer(llm=llm, query=query, context=context):
            yield chunk

        yield sse("citations", {"items": citations})
        yield sse("done", {"ok": True})
    except Exception as e:
        yield sse("error", {"message": str(e)})
        yield sse("done", {"ok": False})


@router.post("/api/chat")
async def chat(payload: dict):
    """
    Expected paylod:
        {
            "collection_id": "default",
            "messages": [{"role": "user", "content": "..."}],
            "k": 5,
            "embedder_provider": "hash" | "sentence-transformers",
        }
    """
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }

    return StreamingResponse(
        _event_stream(payload), headers=headers, media_type="text/event-stream"
    )


@router.post("/api/llm/test")
async def test_llm(payload: dict):
    provider = payload.get("provider")
    model = payload.get("model")
    base_url = payload.get("base_url")
    messages = payload.get("messages") or [{"role": "user", "content": "ping"}]
    max_tokens = payload.get("max_tokens") or 8

    llm = _build_llm_provider(provider, model, base_url)

    try:
        sample = ""
        async for chunk in llm.stream_chat(messages, max_tokens=max_tokens):
            delta = chunk.get("delta")
            if delta:
                sample = delta
                break
        return {"ok": True, "provider": llm.name, "sample": sample}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
