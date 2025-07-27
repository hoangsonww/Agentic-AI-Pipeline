from __future__ import annotations
from typing import Literal, TypedDict

Role = Literal["system", "user", "assistant", "tool"]


class ChatTurn(TypedDict):
    role: Role
    content: str
