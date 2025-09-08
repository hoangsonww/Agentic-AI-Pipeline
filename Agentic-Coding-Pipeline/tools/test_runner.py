"""Utilities for executing test suites."""

from __future__ import annotations

import subprocess
from typing import Tuple


def run_pytest() -> Tuple[int, str]:
    """Run ``pytest`` and return ``(returncode, combined_output)``."""
    result = subprocess.run(["pytest", "-q"], capture_output=True, text=True, check=False)
    output = result.stdout + result.stderr
    return result.returncode, output
