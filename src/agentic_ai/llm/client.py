"""Factory for LangChain chat model instances used by social media and other agents."""

from __future__ import annotations

from ..config import settings


def get_llm():
    """Return a LangChain ChatModel based on the configured MODEL_PROVIDER."""
    if settings.MODEL_PROVIDER.lower() == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=settings.ANTHROPIC_MODEL_CHAT, temperature=0.2)
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=settings.OPENAI_MODEL_CHAT, temperature=0.2)
