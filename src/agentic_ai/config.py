from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    MODEL_PROVIDER: Literal["openai", "anthropic"] = "openai"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL_CHAT: str = "gpt-4o-mini"
    OPENAI_MODEL_EMBED: str = "text-embedding-3-small"

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL_CHAT: str = "claude-3-5-sonnet-latest"

    GOOGLE_API_KEY: str = ""

    CHROMA_DIR: str = ".chroma"
    SQLITE_PATH: str = ".sqlite/agent.db"

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = ".logs"


settings = Settings()
