from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    MODEL_PROVIDER: Literal["openai", "anthropic"] = "openai"

    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL_CHAT: str = "gpt-4o-mini"
    OPENAI_MODEL_EMBED: str = "text-embedding-3-small"

    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL_CHAT: str = "claude-3-5-sonnet-latest"

    CHROMA_DIR: str = os.getenv("CHROMA_DIR", ".chroma")
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", ".sqlite/agent.db")

    # App
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

settings = Settings()
