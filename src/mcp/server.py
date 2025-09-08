"""Minimal MCP server for dispatching tasks to registered pipelines.

This server exposes a small FastAPI application that allows different agentic
pipelines (research outreach, RAG, coding, etc.) to be triggered via a single
interface. Pipelines register a handler function that accepts a task string and
returns a result dictionary. The server routes incoming requests to the
appropriate handler based on the pipeline name.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

PipelineHandler = Callable[[str], Dict[str, Any]]


class PipelineRequest(BaseModel):
    """Incoming request model for executing a pipeline."""

    task: str


class MCPServer:
    """Simple dispatcher for agentic pipelines."""

    def __init__(self) -> None:
        self.app = FastAPI()
        self._pipelines: Dict[str, PipelineHandler] = {}

        @self.app.post("/pipeline/{name}")
        async def run_pipeline(name: str, req: PipelineRequest) -> Dict[str, Any]:
            if name not in self._pipelines:
                raise HTTPException(status_code=404, detail="pipeline not registered")
            handler = self._pipelines[name]
            return handler(req.task)

    def register(self, name: str, handler: PipelineHandler) -> None:
        """Register a pipeline handler under *name*."""

        self._pipelines[name] = handler

    @property
    def pipelines(self) -> Dict[str, PipelineHandler]:
        """Return the mapping of registered pipelines."""

        return dict(self._pipelines)
