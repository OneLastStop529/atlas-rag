from __future__ import annotations

import os
import json
from typing import AsyncIterator, Dict, Any, List, Optional

import httpx

from .base import LLMProvider


class OpenAILLM(LLMProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_s: float = 60,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or ""
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        env_timeout = os.getenv("OPENAI_TIMEOUT_S") or os.getenv("LLM_TIMEOUT_S")
        self.timeout_s = float(env_timeout) if env_timeout else timeout_s
        self.name = f"openai_{self.model}"

    async def stream_chat(
        self, messages: List[Dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[Dict[str, Any]]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI provider.")

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        payload.update(kwargs)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield {"delta": content}
