"""Comprehensive MCP server offering pipeline dispatching and web tooling.

This server exposes a FastAPI application that unifies the different agentic
pipelines (research outreach, RAG, coding, etc.) behind a single interface.  In
addition to the ability for pipelines to register task handlers, it provides
utility endpoints for web search, page browsing and lightweight research
workflows so pipelines share a common toolbox.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

import httpx
import trafilatura
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

PipelineHandler = Callable[[str], Dict[str, Any]]


class PipelineRequest(BaseModel):
    """Incoming request model for executing a pipeline."""

    task: str


class MCPServer:
    """Dispatcher and toolkit for agentic pipelines."""

    def __init__(self) -> None:
        self.app = FastAPI()
        self._pipelines: Dict[str, PipelineHandler] = {}

        @self.app.post("/pipeline/{name}")
        async def run_pipeline(name: str, req: PipelineRequest) -> Dict[str, Any]:
            if name not in self._pipelines:
                raise HTTPException(status_code=404, detail="pipeline not registered")
            handler = self._pipelines[name]
            return handler(req.task)

        @self.app.get("/search")
        async def search(q: str, max_results: int = 5) -> Dict[str, Any]:
            """Perform a web search using DuckDuckGo."""

            with DDGS() as ddgs:
                try:
                    results = list(ddgs.text(q, max_results=max_results))
                except Exception:
                    results = []
            return {"query": q, "results": results}

        @self.app.get("/browse")
        async def browse(url: str) -> Dict[str, Any]:
            """Fetch a web page and return extracted text."""

            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10)
            text = trafilatura.extract(resp.text, url=url)
            if not text:
                soup = BeautifulSoup(resp.text, "lxml")
                text = soup.get_text(" ", strip=True)
            return {"url": url, "text": text}

        @self.app.get("/research")
        async def research(q: str, max_results: int = 3) -> Dict[str, Any]:
            """Conduct a search and fetch the contents of top results."""

            with DDGS() as ddgs:
                try:
                    results = list(ddgs.text(q, max_results=max_results))
                except Exception:
                    results = []
            pages: List[Dict[str, str]] = []
            async with httpx.AsyncClient() as client:
                for res in results:
                    url = res.get("href") or res.get("url")
                    if not url:
                        continue
                    try:
                        resp = await client.get(url, timeout=10)
                        content = trafilatura.extract(resp.text, url=url)
                        pages.append({"url": url, "content": (content or "")[:1000]})
                    except Exception:
                        continue
            return {"query": q, "results": results, "pages": pages}

        @self.app.get("/status")
        async def status() -> Dict[str, Any]:
            """Return server status information."""

            return {"pipelines": list(self._pipelines.keys())}

    def register(self, name: str, handler: PipelineHandler) -> None:
        """Register a pipeline handler under *name*."""

        self._pipelines[name] = handler

    @property
    def pipelines(self) -> Dict[str, PipelineHandler]:
        """Return the mapping of registered pipelines."""

        return dict(self._pipelines)
