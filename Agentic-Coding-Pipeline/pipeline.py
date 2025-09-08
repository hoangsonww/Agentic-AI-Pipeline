"""Orchestration logic for the agentic coding pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable

from agents.base import Agent


@dataclass
class AgenticCodingPipeline:
    """Coordinate coding, formatting, testing and QA agents in an iterative loop."""

    coders: Iterable[Agent]
    formatters: Iterable[Agent] = field(default_factory=list)
    testers: Iterable[Agent] = field(default_factory=list)
    reviewers: Iterable[Agent] = field(default_factory=list)
    max_iterations: int = 3

    def run(self, task: str) -> Dict[str, object]:
        state: Dict[str, object] = {"task": task}
        for _ in range(self.max_iterations):
            for coder in self.coders:
                state = coder.run(state)
                if not state.get("proposed_code"):
                    state["status"] = "failed"
                    state["reason"] = "coder did not return code"
                    return state

            for formatter in self.formatters:
                state = formatter.run(state)

            tests_ok = True
            for tester in self.testers:
                state = tester.run(state)
                if not state.get("tests_passed"):
                    tests_ok = False
                    state["feedback"] = state.get("test_output", "")
                    break
            if not tests_ok:
                continue

            reviews_ok = True
            for reviewer in self.reviewers:
                state = reviewer.run(state)
                if not state.get("qa_passed"):
                    reviews_ok = False
                    state["feedback"] = state.get("qa_output", "")
                    break
            if reviews_ok:
                state["status"] = "completed"
                return state

        state.setdefault("status", "failed")
        return state
