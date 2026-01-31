import asyncio
import json
import re
from typing import Any, AsyncGenerator, List

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.providers.factory import get_llm_provider
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
    }


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
        llm = get_llm_provider()
        query = llm.latest_user_text(params["messages"])

        if not query:
            yield sse("error", {"message": "No user query found in messages"})
            yield sse("done", {})
            return

        chunks = retrieve_top_k(
            query=query,
            collection_id=params["collection_id"],
            k=params["k"],
            embedder_provider=params["embedder_provider"],
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
