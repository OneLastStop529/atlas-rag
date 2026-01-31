from __future__ import annotations

import json
import os
from typing import AsyncIterator, Dict, Any, List, Optional

import httpx

from .base import LLMProvider


class OllamaLocal(LLMProvider):
    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_s: float = 60,
    ) -> None:
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.base_url = (
            base_url or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
        ).rstrip("/")
        self.timeout_s = timeout_s
        self.name = f"ollama_{self.model}"

    async def stream_chat(
        self, messages: List[Dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[Dict[str, Any]]:
        prompt = self.messages_to_prompt(messages)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
        }
        payload.update(kwargs)
        print("Ollama payload:", payload)

        url = f"{self.base_url}/api/generate"
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            async with client.stream(
                "POST", url, headers={"Content-Type": "application/json"}, json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    response = chunk.get("response") or {}
                    if response:
                        yield {"delta": response}
                    if chunk.get("done") is True:
                        break
