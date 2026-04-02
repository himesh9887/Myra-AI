from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "MYRA Backend"
    environment: str = "development"
    api_prefix: str = "/api"
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "myra"
    timezone: str = "Asia/Kolkata"
    short_term_memory_limit: int = 24
    long_term_memory_limit: int = 100
    relevance_window: int = 100
    reminder_poll_seconds: int = 60
    default_reminder_lead_minutes: int = 120
    use_embeddings: bool = False
    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

