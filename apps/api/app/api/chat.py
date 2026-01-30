from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json
import asyncio
import re
from typing import Any, List
from typing import AsyncGenerator
from app.rag.retriever import build_context, retrieve_top_k, to_citations


router = APIRouter()


def sse(event: str, data: dict) -> str:
    """Format data as Server-Sent Events (SSE)."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _latest_user_text(messages: List[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message["role"] == "user":
            return message["content"]
    return ""


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


@router.post("/chat")
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
    collection_id: str = payload.get("collection_id") or "default"
    messages = payload.get("messages") or []
    k = int(payload.get("k") or 5)

    embedder_provider: str = payload.get("embedder_provider") or "hash"

    query = _latest_user_text(messages)

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            if not query:
                yield sse("error", {"message": "No user query found in messages"})
                yield sse("done", {})
                return

            chunks = retrieve_top_k(
                query=query,
                collection_id=collection_id,
                k=k,
                embedder_provider=embedder_provider,
            )
            context = build_context(chunks, max_chars=4000)
            citations = to_citations(chunks)

            answer = _v0_answer(query, context)

            async for tok in _stream_text_as_tokens(answer):
                yield sse("token", {"delta": tok})

            yield sse("citations", {"items": citations})
            yield sse("done", {"ok": True})

        except Exception as e:
            yield sse("error", {"message": str(e)})
            yield sse("done", {"ok": False})

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }

    return StreamingResponse(
        event_stream(), headers=headers, media_type="text/event-stream"
    )
