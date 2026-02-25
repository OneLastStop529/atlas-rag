import json
from typing import AsyncGenerator


def sse(event: str, data: dict) -> str:
    """Format data as Server-Sent Events (SSE)."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def stream_llm_answer(
    *, llm, query: str, context: str
) -> AsyncGenerator[str, None]:
    llm_messages = llm.build_llm_messages(query=query, context=context)
    async for chunk in llm.stream_chat(llm_messages):
        delta = chunk.get("delta")
        if delta:
            yield sse("token", {"delta": delta})
