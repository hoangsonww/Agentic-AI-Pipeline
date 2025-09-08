"""Quality assurance agents performing LLM-based code review."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from agentic_ai.llm import LLMClient, OpenAIClient

from .base import BaseAgent


@dataclass
class QAAgent(BaseAgent):
    """Ask an LLM to review code for quality issues."""

    llm: LLMClient | None = None

    def __post_init__(self) -> None:  # pragma: no cover
        if self.llm is None:
            self.llm = OpenAIClient()

    def run(self, state: Dict[str, object]) -> Dict[str, object]:
        code = state.get("proposed_code", "")
        prompt = (
            "Review the following Python code for bugs or style issues. "
            "Respond with PASS if the code is acceptable, otherwise describe the problems.\n"
            + code
        )
        review = self.llm.complete(prompt)
        state["qa_passed"] = "pass" in review.lower()
        state["qa_output"] = review
        return state
