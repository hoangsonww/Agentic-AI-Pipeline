"""Tests for the shared MCP server."""

from __future__ import annotations

from typing import Dict
from unittest.mock import patch

from fastapi.testclient import TestClient
from mcp import MCPServer


def test_register_and_call_pipeline() -> None:
    server = MCPServer()

    def handler(task: str) -> Dict[str, object]:
        return {"echo": task}

    server.register("echo", handler)

    client = TestClient(server.app)
    resp = client.post("/pipeline/echo", json={"task": "hi"})
    assert resp.status_code == 200
    assert resp.json() == {"echo": "hi"}


def test_web_tooling() -> None:
    server = MCPServer()
    client = TestClient(server.app)

    search = client.get("/search", params={"q": "python", "max_results": 1})
    assert search.status_code == 200
    assert "results" in search.json()

    browse = client.get("/browse", params={"url": "https://example.com"})
    assert browse.status_code == 200
    assert "illustrative examples" in browse.json()["text"]

    research = client.get("/research", params={"q": "Example Domain", "max_results": 1})
    assert research.status_code == 200
    data = research.json()
    assert "results" in data and "pages" in data


def test_llm_endpoint() -> None:
    server = MCPServer()
    client = TestClient(server.app)

    with patch("agentic_ai.llm.clients.OpenAIClient.complete", return_value="hi"):
        resp = client.post("/llm/openai", json={"prompt": "hello"})
    assert resp.status_code == 200
    assert resp.json()["completion"] == "hi"
