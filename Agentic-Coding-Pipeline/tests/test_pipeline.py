"""Tests for the agentic coding pipeline orchestration."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

sys.path.append(str(Path(__file__).resolve().parents[1]))

from agentic_coding_pipeline.agents.base import BaseAgent
from agentic_coding_pipeline.pipeline import AgenticCodingPipeline


@dataclass
class DummyCodingAgent(BaseAgent):
    def run(self, state: Dict[str, object]) -> Dict[str, object]:
        state["proposed_code"] = "print('hello')"
        return state


@dataclass
class DummyTestingAgent(BaseAgent):
    def run(self, state: Dict[str, object]) -> Dict[str, object]:
        state["tests_passed"] = True
        state["test_output"] = "tests passed"
        return state


@dataclass
class DummyQAAgent(BaseAgent):
    def run(self, state: Dict[str, object]) -> Dict[str, object]:
        state["qa_passed"] = True
        state["qa_output"] = "lint clean"
        return state


def test_pipeline_completes() -> None:
    pipeline = AgenticCodingPipeline(
        coder=DummyCodingAgent(name="coder"),
        testers=[DummyTestingAgent(name="tester")],
        reviewers=[DummyQAAgent(name="qa")],
    )
    result = pipeline.run("do something")
    assert result["status"] == "completed"
    assert result["proposed_code"] == "print('hello')"
