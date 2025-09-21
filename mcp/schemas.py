from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class PipelineRequest(BaseModel):
    task: str


class LLMRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    provider: Optional[str] = None


class SummarizeRequest(BaseModel):
    text: str
    provider: Optional[str] = None
    model: Optional[str] = None


class KBAddRequest(BaseModel):
    id: Optional[str] = None
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FileWriteRequest(BaseModel):
    path: str
    content: str

