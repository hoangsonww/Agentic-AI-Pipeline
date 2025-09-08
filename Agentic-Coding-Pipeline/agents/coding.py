"""Agents that generate or modify code using LLMs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from agentic_ai.llm import LLMClient, OpenAIClient

from .base import BaseAgent


@dataclass
class CodingAgent(BaseAgent):
    """Agent that uses an LLM to produce code changes."""

    llm: LLMClient | None = None

    def __post_init__(self) -> None:  # pragma: no cover - simple init
        if self.llm is None:
            self.llm = OpenAIClient()

    def run(self, state: Dict[str, object]) -> Dict[str, object]:
        prompt = state.get("task", "")
        prompt = (
            "Write a single Python function solving the following task. "
            "Return only code.\n" + str(prompt)
        )
        content = self.llm.complete(prompt)
        state["proposed_code"] = content
        return state
