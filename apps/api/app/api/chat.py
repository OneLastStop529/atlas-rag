from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json
import asyncio


router = APIRouter()


def sse(event: str, data: dict) -> str:
    """Format data as Server-Sent Events (SSE)."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/chat")
async def chat(payload:dict):
    async def stream():
        for token in ["Hello", " ", "from", " ", "atlas", "rag"]:
            yield sse("token", {"delta": token})
            await asyncio.sleep(0.05) # Simulate delay

        yield sse("citations" ,{
            "items": [
                {"source": "example.pdf", "page": 1, "snippet": "Example text"}
            ]
        })

        yield sse("done", {"ok": True})

    return StreamingResponse(stream(), media_type="text/event-stream")


