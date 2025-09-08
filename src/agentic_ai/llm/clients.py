"""Lightweight LLM client wrappers for OpenAI, Anthropic Claude and Google Gemini.

These clients expose a minimal `complete` method that posts directly to the
vendor's HTTP API. They intentionally avoid heavy SDK dependencies so they can
be reused across all pipelines.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Protocol

import httpx


class LLMClient(Protocol):
    """Protocol for minimal text completion clients."""

    def complete(self, prompt: str) -> str:  # pragma: no cover - interface
        ...


@dataclass
class OpenAIClient:
    """Call OpenAI's Chat Completions API."""

    model: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    base_url: str = "https://api.openai.com/v1"

    def complete(self, prompt: str) -> str:
        key = self.api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set")
        headers = {"Authorization": f"Bearer {key}"}
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


@dataclass
class ClaudeClient:
    """Call Anthropic's Messages API."""

    model: str = "claude-3-opus-20240229"
    api_key: Optional[str] = None
    base_url: str = "https://api.anthropic.com/v1"

    def complete(self, prompt: str) -> str:
        key = self.api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        resp = httpx.post(f"{self.base_url}/messages", headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"].strip()


@dataclass
class GeminiClient:
    """Call Google's Generative Language API (Gemini)."""

    model: str = "gemini-1.5-pro"
    api_key: Optional[str] = None
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    def complete(self, prompt: str) -> str:
        key = self.api_key or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY not set")
        url = f"{self.base_url}/models/{self.model}:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        resp = httpx.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


__all__ = [
    "LLMClient",
    "OpenAIClient",
    "ClaudeClient",
    "GeminiClient",
]
