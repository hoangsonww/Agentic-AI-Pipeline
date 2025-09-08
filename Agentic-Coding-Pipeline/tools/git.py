"""Helpers for interacting with git repositories."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable


def commit(files: Iterable[Path], message: str) -> None:
    """Add *files* to git and create a commit with *message*."""
    paths = [str(Path(f)) for f in files]
    subprocess.run(["git", "add", *paths], check=True)
    subprocess.run(["git", "commit", "-m", message], check=True)
