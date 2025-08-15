from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Evidence(BaseModel):
    doc_id: str
    chunk_id: str
    text: str
    meta: Dict[str, Any] = Field(default_factory=dict)

class AgentResult(BaseModel):
    output: Any
    evidence: List[Evidence] = Field(default_factory=list)
    cost: Dict[str, Any] = Field(default_factory=dict)
