from __future__ import annotations
from typing import Protocol, AsyncIterator, List, Dict, Any


class LLMProvider(Protocol):
    name: str

    async def stream_chat(
        self, messages: List[Dict[str, Any]], **kwargs
    ) -> AsyncIterator[Dict[str, Any]]: ...
