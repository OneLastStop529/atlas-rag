import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str | None = None
    adv_retrieval_enabled: bool = False
    adv_retrieval_allow_request_override: bool = False
    retrieval_strategy: str = "baseline"
    reranker_variant: str = "rrf_simple"
    query_rewrite_policy: str = "disabled"
    adv_retrieval_rollout_percent: int = Field(default=0, ge=0, le=100)

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")


# Allow env var to override and avoid raising if missing during imports
settings = Settings()
# Fallback to environment variable if provided outside pydantic
if not settings.database_url:
    settings.database_url = os.getenv("DATABASE_URL")
