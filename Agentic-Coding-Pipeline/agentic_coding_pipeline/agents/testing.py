"""Agents responsible for executing test suites."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Dict

from .base import BaseAgent


@dataclass
class TestingAgent(BaseAgent):
    """Run `pytest` and report whether tests pass."""

    def run(self, state: Dict[str, object]) -> Dict[str, object]:
        result = subprocess.run(["pytest", "-q"], capture_output=True, text=True, check=False)
        state["tests_passed"] = result.returncode == 0
        state["test_output"] = result.stdout + result.stderr
        return state
