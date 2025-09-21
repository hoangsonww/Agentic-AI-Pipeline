from __future__ import annotations
import json, anyio
import httpx
from typing import AsyncIterator, Callable

class AgenticAIClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 60.0):
        self.base = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=timeout)

    async def new_chat(self) -> dict:
        r = await self.client.get(f"{self.base}/api/new_chat")
        r.raise_for_status()
        return r.json()

    async def ingest(self, text: str, metadata: dict | None = None) -> dict:
        r = await self.client.post(f"{self.base}/api/ingest", json={"text": text, "metadata": metadata or {}})
        r.raise_for_status()
        return r.json()

    async def ingest_url(self, url: str, metadata: dict | None = None) -> dict:
        r = await self.client.post(f"{self.base}/api/ingest_url", json={"url": url, "metadata": metadata or {}})
        r.raise_for_status()
        return r.json()

    async def ingest_file(self, file_path: str, title: str | None = None, tags: list[str] | None = None) -> dict:
        import os
        p = os.path.abspath(file_path)
        name = os.path.basename(p)
        with open(p, "rb") as f:
            files = {"file": (name, f, "application/octet-stream")}
            data = {}
            if title: data["title"] = title
            if tags: data["tags"] = ",".join(tags)
            r = await self.client.post(f"{self.base}/api/ingest_file", files=files, data=data)
            r.raise_for_status()
            return r.json()

    async def feedback(self, chat_id: str, rating: int, comment: str | None = None, message_id: int | None = None) -> dict:
        r = await self.client.post(f"{self.base}/api/feedback", json={"chat_id": chat_id, "rating": rating, "comment": comment, "message_id": message_id})
        r.raise_for_status()
        return r.json()

    async def chat_stream(self, message: str, chat_id: str | None = None, on_token: Callable[[str], None] | None = None) -> dict:
        r = await self.client.post(f"{self.base}/api/chat", json={"chat_id": chat_id, "message": message})
        r.raise_for_status()
        # naive SSE parsing
        async for chunk in r.aiter_text():
            for block in chunk.split("\n\n"):
                if not block.strip():
                    continue
                ev = None; data = None
                for line in block.splitlines():
                    if line.startswith("event:"):
                        ev = line[6:].strip()
                    elif line.startswith("data:"):
                        data = line[5:]
                if ev == "token" and data and on_token:
                    on_token(data)
                if ev == "done" and data:
                    try:
                        return json.loads(data)
                    except Exception:
                        return {"chat_id": chat_id or ""}
        return {"chat_id": chat_id or ""}

    # -------- Agentic Coding Pipeline --------
    async def coding_run(self, repo: str | None = None, github: str | None = None, jira: str | None = None, task: str | None = None) -> dict:
        r = await self.client.post(f"{self.base}/api/coding/run", json={"repo": repo, "github": github, "jira": jira, "task": task})
        r.raise_for_status()
        return r.json()

    async def coding_stream(self, repo: str | None = None, github: str | None = None, jira: str | None = None, task: str | None = None, on_event: Callable[[str, str], None] | None = None) -> None:
        r = await self.client.post(f"{self.base}/api/coding/stream", json={"repo": repo, "github": github, "jira": jira, "task": task})
        r.raise_for_status()
        async for chunk in r.aiter_text():
            for block in chunk.split("\n\n"):
                if not block.strip():
                    continue
                ev = None; data = None
                for line in block.splitlines():
                    if line.startswith("event:"): ev = line[6:].strip()
                    elif line.startswith("data:"): data = line[5:]
                if ev and data and on_event:
                    on_event(ev, data)

    # -------- Agentic RAG Pipeline --------
    async def rag_new_session(self) -> dict:
        r = await self.client.get(f"{self.base}/api/rag/new_session")
        r.raise_for_status()
        return r.json()

    async def rag_ask_stream(self, question: str, session_id: str | None = None, on_event: Callable[[str, str], None] | None = None) -> None:
        payload = {"session_id": session_id, "question": question}
        r = await self.client.post(f"{self.base}/api/rag/ask", json=payload)
        r.raise_for_status()
        async for chunk in r.aiter_text():
            for block in chunk.split("\n\n"):
                if not block.strip():
                    continue
                ev = None; data = None
                for line in block.splitlines():
                    if line.startswith("event:"): ev = line[6:].strip()
                    elif line.startswith("data:"): data = line[5:]
                if ev and data and on_event:
                    on_event(ev, data)

    async def rag_ingest_text(self, text: str | None = None, url: str | None = None, title: str | None = None, tags: list[str] | None = None) -> dict:
        payload: dict = {}
        if text: payload["text"] = text
        if url: payload["url"] = url
        if title: payload["title"] = title
        if tags: payload["tags"] = tags
        r = await self.client.post(f"{self.base}/api/rag/ingest_text", json=payload)
        r.raise_for_status()
        return r.json()

    async def rag_ingest_file(self, file_path: str, title: str | None = None, tags: list[str] | None = None) -> dict:
        import os
        p = os.path.abspath(file_path)
        name = os.path.basename(p)
        with open(p, "rb") as f:
            files = {"file": (name, f, "application/octet-stream")}
            data = {}
            if title: data["title"] = title
            if tags: data["tags"] = ",".join(tags)
            r = await self.client.post(f"{self.base}/api/rag/ingest_file", files=files, data=data)
            r.raise_for_status()
            return r.json()

    async def aclose(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.aclose()
