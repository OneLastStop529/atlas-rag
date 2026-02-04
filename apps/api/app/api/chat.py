import asyncio
import json
import os
import re
from typing import Any, AsyncGenerator, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.providers.factory import get_llm_provider
from app.providers.llm.openai_llm import OpenAILLM
from app.providers.llm.ollama_local import OllamaLocal
from app.rag.retriever import build_context, retrieve_top_k, to_citations


router = APIRouter()


def sse(event: str, data: dict) -> str:
    """Format data as Server-Sent Events (SSE)."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _v0_answer(query: str, context: str) -> str:
    """
    v0 synthesizer: no LLM yet.
    Gives you a deterministic response to validate the RAG pipeline
    Replace this later with a real LLM stream.
    """
    if not context.strip():
        return f"I couldn't find any relevant information for your query: '{query}'."

    return (
        "Here are the most relevant snippets I found in your documents.\n\n"
        "----\n"
        f"Question: {query}\n"
        "----\n\n"
        f"{context}\n\n"
        "----\n"
        "Next step: replace this synthesizer with a real LLM-based one!"
    )


async def _stream_text_as_tokens(
    text: str, delay: float = 0.005
) -> AsyncGenerator[str, None]:
    """
    Simple token streamer: streams whitespace-aware chunks (works well for validating UI).
    Switch to word or real LLM deltas later.
    """
    for token in re.findall(r"\S+|\s+", text):
        yield token
        if delay:
            await asyncio.sleep(delay)


def _parse_payload(payload: dict) -> dict[str, Any]:
    return {
        "collection_id": payload.get("collection_id") or "default",
        "messages": payload.get("messages") or [],
        "k": int(payload.get("k") or 5),
        "embedder_provider": payload.get("embedder_provider") or "hash",
        "use_reranking": bool(payload.get("use_reranking", False)),
        "llm_provider": payload.get("llm_provider"),
        "llm_model": payload.get("llm_model"),
        "llm_base_url": payload.get("llm_base_url"),
    }


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
        params = _parse_payload(payload)
        if params["llm_provider"] or params["llm_model"] or params["llm_base_url"]:
            llm = _build_llm_provider(
                params["llm_provider"], params["llm_model"], params["llm_base_url"]
            )
        else:
            llm = get_llm_provider()
        query = llm.latest_user_text(params["messages"])

        if not query:
            yield sse("error", {"message": "No user query found in messages"})
            yield sse("done", {})
            return

        print(params)

        chunks = retrieve_top_k(
            query=query,
            collection_id=params["collection_id"],
            k=params["k"],
            embedder_provider=params["embedder_provider"],
            use_reranking=params["use_reranking"],
        )
        print(f"retrieval_count={len(chunks)} collection_id={params['collection_id']}")
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
