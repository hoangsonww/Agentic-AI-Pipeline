"""Agents that generate or modify code using LLMs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from openai import OpenAI

from .base import BaseAgent


@dataclass
class CodingAgent(BaseAgent):
    """Agent that uses an LLM to produce code changes."""

    model: str = "gpt-4o-mini"

    def run(self, state: Dict[str, object]) -> Dict[str, object]:
        client = OpenAI()
        prompt = state.get("task", "")
        messages = [
            {"role": "system", "content": "You are an autonomous software engineer."},
            {"role": "user", "content": str(prompt)},
        ]
        response = client.chat.completions.create(model=self.model, messages=messages)
        content = response.choices[0].message.content
        state["proposed_code"] = content
        return state
