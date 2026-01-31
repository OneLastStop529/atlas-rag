from __future__ import annotations

import os
from typing import Any, AsyncIterator, Dict, List


class LLMProvider:
    name: str

    def latest_user_text(self, messages: List[dict[str, Any]]) -> str:
        for message in reversed(messages):
            if message["role"] == "user":
                return message["content"]
        return ""

    def build_llm_messages(self, query: str, context: str) -> List[Dict[str, Any]]:
        default_prompt = (
            "You are an AI assistant helping users by providing information "
            "based on the provided context. Use the context to answer the user's "
            "questions accurately and concisely. "
            "If the answer is not contained within the context, say 'I don't know.'\n"
            "CONTEXT:\n"
            "{context}\n"
        )
        template = os.getenv("LLM_SYSTEM_PROMPT", default_prompt)
        try:
            system_prompt = template.format(context=context, query=query)
        except KeyError:
            system_prompt = default_prompt.format(context=context, query=query)
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

    def messages_to_prompt(self, messages: List[Dict[str, Any]]) -> str:
        prompt = ""
        for message in messages:
            role = message["role"]
            content = message["content"]
            if role == "system":
                prompt += f"System: {content}\n"
            elif role == "user":
                prompt += f"User: {content}\n"
            elif role == "assistant":
                prompt += f"Assistant: {content}\n"
        return prompt

    async def stream_chat(
        self, messages: List[Dict[str, Any]], **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        raise NotImplementedError
