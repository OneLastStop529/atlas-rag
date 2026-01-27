from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    database_url: str | None = None

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")


# Allow env var to override and avoid raising if missing during imports
settings = Settings()
# Fallback to environment variable if provided outside pydantic
if not settings.database_url:
    settings.database_url = os.getenv("DATABASE_URL")
