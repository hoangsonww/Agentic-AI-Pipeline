"""Quality assurance agents performing static analysis and linting."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Dict

from .base import BaseAgent


@dataclass
class QAAgent(BaseAgent):
    """Run `ruff` linter to ensure code style and quality."""

    def run(self, state: Dict[str, object]) -> Dict[str, object]:
        result = subprocess.run(["ruff", "."], capture_output=True, text=True, check=False)
        state["qa_passed"] = result.returncode == 0
        state["qa_output"] = result.stdout + result.stderr
        return state
