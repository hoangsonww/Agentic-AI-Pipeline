"""Agents responsible for generating and executing tests with an LLM."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict

from agentic_ai.llm import LLMClient, OpenAIClient

from .base import BaseAgent


@dataclass
class TestingAgent(BaseAgent):
    """Generate pytest tests via an LLM and execute them."""

    llm: LLMClient | None = None

    def __post_init__(self) -> None:  # pragma: no cover
        if self.llm is None:
            self.llm = OpenAIClient()

    def run(self, state: Dict[str, object]) -> Dict[str, object]:
        code = state.get("proposed_code", "")
        prompt = (
            "Write pytest tests for the following Python code. "
            "Return only the test file contents.\n"
            + code
        )
        tests = self.llm.complete(prompt)
        with TemporaryDirectory() as td:
            work = Path(td)
            (work / "solution.py").write_text(code)
            (work / "test_solution.py").write_text(tests)
            result = subprocess.run(
                ["pytest", "-q"], cwd=work, capture_output=True, text=True, check=False
            )
        state["tests_passed"] = result.returncode == 0
        state["test_output"] = result.stdout + result.stderr
        return state
