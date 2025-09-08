"""Tests for the agentic coding pipeline orchestration using LLM-backed agents."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agents.coding import CodingAgent
from agents.formatting import FormattingAgent
from agents.qa import QAAgent
from agents.testing import TestingAgent
from pipeline import AgenticCodingPipeline


class MockLLM:
    """Simple mock LLM returning canned responses."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete(self, prompt: str) -> str:  # pragma: no cover - trivial
        self.calls.append(prompt)
        if "tests" in prompt:
            return (
                "from solution import add\n\n"
                "def test_add():\n    assert add(1, 2) == 3\n"
            )
        if "Review" in prompt:
            return "PASS"
        return "def add(a, b):\n    return a + b\n"


def test_pipeline_completes() -> None:
    llm = MockLLM()
    pipeline = AgenticCodingPipeline(
        coders=[CodingAgent(name="gpt-coder", llm=llm), CodingAgent(name="claude-coder", llm=llm)],
        formatters=[FormattingAgent(name="fmt")],
        testers=[TestingAgent(name="tester", llm=llm)],
        reviewers=[QAAgent(name="qa", llm=llm)],
    )
    result = pipeline.run("add two numbers")
    assert result["status"] == "completed"
    assert "def add" in result["proposed_code"]
