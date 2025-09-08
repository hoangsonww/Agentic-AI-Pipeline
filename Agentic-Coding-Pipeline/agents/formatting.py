"""Agents that format code using Ruff's auto-fix capabilities."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict

from .base import BaseAgent


@dataclass
class FormattingAgent(BaseAgent):
    """Run Ruff formatting on the proposed code."""

    def run(self, state: Dict[str, object]) -> Dict[str, object]:
        code = state.get("proposed_code")
        if not code:
            return state
        with TemporaryDirectory() as td:
            path = Path(td) / "solution.py"
            path.write_text(str(code))
            subprocess.run(["ruff", "--fix", str(path)], capture_output=True, check=False)
            state["proposed_code"] = path.read_text()
        return state
