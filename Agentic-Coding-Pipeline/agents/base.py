"""Base definitions for agents used in the coding pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Protocol


class Agent(Protocol):
    """Protocol that all agents must follow."""

    name: str

    def run(self, state: Dict[str, object]) -> Dict[str, object]:
        """Execute the agent's task and update the shared state."""
        ...


@dataclass
class BaseAgent:
    """Simple base class implementing :class:`Agent` interface."""

    name: str

    def run(self, state: Dict[str, object]) -> Dict[str, object]:
        raise NotImplementedError
