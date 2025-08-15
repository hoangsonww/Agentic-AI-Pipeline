from typing import Any
from pydantic import BaseModel
from core.structs import AgentResult

class Agent(BaseModel):
    name: str = "agent"
    system_prompt: str = ""

    def run(self, **kwargs) -> AgentResult:
        raise NotImplementedError
