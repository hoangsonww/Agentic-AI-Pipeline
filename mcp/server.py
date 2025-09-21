"""Comprehensive MCP server offering pipeline dispatching and web tooling.

This server exposes a FastAPI application that unifies the different agentic
pipelines (research outreach, RAG, coding, etc.) behind a single interface. In
addition to the ability for pipelines to register task handlers, it provides
utility endpoints for web search, page browsing, lightweight research workflows
and direct LLM access so pipelines share a common toolbox.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import httpx
import trafilatura
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from fastapi import FastAPI, HTTPException, Body
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from agentic_ai.llm import ClaudeClient, GeminiClient, OpenAIClient
from .schemas import PipelineRequest, LLMRequest, SummarizeRequest, KBAddRequest, FileWriteRequest
from .tools import web as webtools
from .tools import kb as kbtools
from .tools import files as filestools

PipelineHandler = Callable[[str], Dict[str, Any]]


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

        @self.app.post("/llm/{provider}")
        async def llm(provider: str, req: LLMRequest) -> Dict[str, Any]:
            mapping = {
                "openai": OpenAIClient,
                "claude": ClaudeClient,
                "gemini": GeminiClient,
            }
            if provider not in mapping:
                raise HTTPException(status_code=404, detail="unknown provider")
            client = mapping[provider](model=req.model) if req.model else mapping[provider]()
            try:
                completion = client.complete(req.prompt)
            except Exception as exc:  # pragma: no cover - network issues
                raise HTTPException(status_code=500, detail=str(exc))
            return {"provider": provider, "completion": completion}

        @self.app.post("/llm/summarize")
        async def summarize(req: SummarizeRequest) -> Dict[str, Any]:
            prov = (req.provider or "openai").lower()
            mapping = {
                "openai": OpenAIClient,
                "claude": ClaudeClient,
                "gemini": GeminiClient,
            }
            if prov not in mapping:
                raise HTTPException(status_code=400, detail="unknown provider")
            client = mapping[prov](model=req.model) if req.model else mapping[prov]()
            prompt = f"Summarize the following text concisely with key bullets.\n\n{req.text}"
            out = client.complete(prompt)
            return {"provider": prov, "summary": out}

        @self.app.get("/search")
        async def search(q: str, max_results: int = 5) -> Dict[str, Any]:
            """Perform a web search using DuckDuckGo."""
            results = await webtools.search_ddg(q, max_results=max_results)
            return {"query": q, "results": results}

        @self.app.get("/browse")
        async def browse(url: str) -> Dict[str, Any]:
            """Fetch a web page and return extracted text."""
            text = await webtools.fetch_page(url)
            return {"url": url, "text": text}

        @self.app.get("/research")
        async def research(q: str, max_results: int = 3) -> Dict[str, Any]:
            """Conduct a search and fetch the contents of top results."""
            results = await webtools.search_ddg(q, max_results=max_results)
            pages: List[Dict[str, str]] = []
            for res in results:
                url = res.get("href") or res.get("url")
                if not url:
                    continue
                try:
                    content = await webtools.fetch_page(url)
                    pages.append({"url": url, "content": (content or "")[:1000]})
                except Exception:
                    continue
            return {"query": q, "results": results, "pages": pages}

        # ---- KB ----
        @self.app.post("/kb/add")
        async def kb_add(req: KBAddRequest) -> Dict[str, Any]:
            return kbtools.kb_add(req.id, req.text, req.metadata)

        @self.app.get("/kb/search")
        async def kb_search(q: str, k: int = 5) -> Dict[str, Any]:
            return {"query": q, "results": kbtools.kb_search(q, k=k)}

        # ---- Files (sandboxed) ----
        @self.app.post("/fs/write")
        async def fs_write(req: FileWriteRequest) -> Dict[str, Any]:
            return filestools.write_file(req.path, req.content)

        @self.app.get("/fs/read")
        async def fs_read(path: str) -> Dict[str, Any]:
            return filestools.read_file(path)

        # ---- Pipeline Streams (adapters) ----
        @self.app.post("/pipeline/coding/stream")
        async def coding_stream(payload: dict = Body(...)):
            root = __import__("pathlib").Path(__file__).resolve().parents[1]
            import sys as _sys
            _sys.path.append(str(root / "Agentic-Coding-Pipeline"))
            try:
                from services import run_pipeline_stream as _coding_stream  # type: ignore
            except Exception as e:  # pragma: no cover
                raise HTTPException(status_code=500, detail=f"coding services unavailable: {e}")

            def gen():
                for ev, data in _coding_stream(
                    repo_input=payload.get("repo"), jira=payload.get("jira"), github=payload.get("github"), text=payload.get("task")
                ):
                    yield {"event": ev, "data": data}
            return EventSourceResponse(gen())

        @self.app.post("/pipeline/rag/ask")
        async def rag_stream(payload: dict = Body(...)):
            root = __import__("pathlib").Path(__file__).resolve().parents[1]
            import sys as _sys
            _sys.path.append(str(root / "Agentic-RAG-Pipeline"))
            try:
                from services import run_rag_stream as _rag_stream, new_session as _rag_new_session  # type: ignore
            except Exception as e:  # pragma: no cover
                raise HTTPException(status_code=500, detail=f"rag services unavailable: {e}")
            session_id = payload.get("session_id") or _rag_new_session()
            question = (payload.get("question") or "").strip()
            if not question:
                raise HTTPException(status_code=400, detail="question required")

            def gen():
                for ev, data in _rag_stream(session_id=session_id, query=question):
                    yield {"event": ev, "data": data}
            return EventSourceResponse(gen())

        @self.app.post("/pipeline/data/analyze")
        async def data_stream(payload: dict = Body(...)):
            root = __import__("pathlib").Path(__file__).resolve().parents[1]
            import sys as _sys
            _sys.path.append(str(root / "Agentic-Data-Pipeline"))
            try:
                from services import run_data_stream as _data_stream  # type: ignore
            except Exception as e:  # pragma: no cover
                raise HTTPException(status_code=500, detail=f"data services unavailable: {e}")
            source = (payload.get("source") or "text").strip()
            dataset = payload.get("dataset") or ""
            task = payload.get("task")
            if not dataset:
                raise HTTPException(status_code=400, detail="dataset required")
            def gen():
                for ev, data in _data_stream(source=source, dataset=dataset, task=task):
                    yield {"event": ev, "data": data}
            return EventSourceResponse(gen())

        @self.app.get("/status")
        async def status() -> Dict[str, Any]:
            """Return server status information."""
            return {"pipelines": list(self._pipelines.keys())}

        @self.app.get("/pipelines")
        async def pipelines_list() -> Dict[str, Any]:
            return {"pipelines": list(self._pipelines.keys())}

    def register(self, name: str, handler: PipelineHandler) -> None:
        """Register a pipeline handler under *name*."""
        self._pipelines[name] = handler

    @property
    def pipelines(self) -> Dict[str, PipelineHandler]:
        """Return the mapping of registered pipelines."""
        return dict(self._pipelines)


def create_app() -> FastAPI:
    """Factory for ASGI servers (e.g., uvicorn mcp.server:create_app --factory)"""
    return MCPServer().app
