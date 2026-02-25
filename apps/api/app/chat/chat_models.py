from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    collection_id: str = "default"
    messages: list[ChatMessage] = Field(default_factory=list)
    k: int = Field(default=5, ge=1, le=50)
    embeddings_provider: str | None = None
    retriever_provider: str | None = None
    use_reranking: bool = False
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    adv_retrieval_enabled: bool | None = None
    retrieval_strategy: str | None = None
    reranker_variant: str | None = None
    query_rewrite_policy: str | None = None
    adv_retrieval_eval_mode: str | None = None
    adv_retrieval_eval_sample_percent: int | None = None
    adv_retrieval_eval_timeout_ms: int | None = None


@dataclass(frozen=True)
class ChatExecutionContext:
    params: ChatRequest
    llm: Any
    query: str
    advanced_cfg: Any
    retrieval_plan: Any
    log_ctx: dict[str, Any]
