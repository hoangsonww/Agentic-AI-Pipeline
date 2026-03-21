"""Tests for the shared MCP server."""

from __future__ import annotations

from typing import Dict
from unittest.mock import AsyncMock, patch

import httpx
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
    """Test web search, browse, and research endpoints with mocked network calls."""
    server = MCPServer()
    client = TestClient(server.app)

    # Mock DuckDuckGo search
    mock_results = [{"title": "Python", "href": "https://example.com", "body": "A language"}]
    with patch("mcp.tools.web.DDGS") as mock_ddgs:
        mock_ddgs.return_value.__enter__ = lambda s: s
        mock_ddgs.return_value.__exit__ = lambda s, *a: None
        mock_ddgs.return_value.text.return_value = mock_results

        search = client.get("/search", params={"q": "python", "max_results": 1})
        assert search.status_code == 200
        assert "results" in search.json()

    # Mock httpx + trafilatura for browse
    html = "<html><body>Example Domain for illustrative examples</body></html>"
    mock_response = httpx.Response(200, text=html)
    with patch("mcp.tools.web.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_instance.get.return_value = mock_response

        extract_rv = "illustrative examples in documents"
        with patch("mcp.tools.web.trafilatura.extract", return_value=extract_rv):
            browse = client.get("/browse", params={"url": "https://example.com"})
            assert browse.status_code == 200
            assert "illustrative examples" in browse.json()["text"]

    # Mock research (search + fetch combined)
    with (
        patch("mcp.tools.web.DDGS") as mock_ddgs,
        patch("mcp.tools.web.httpx.AsyncClient") as mock_client,
        patch("mcp.tools.web.trafilatura.extract", return_value="page content"),
    ):
        mock_ddgs.return_value.__enter__ = lambda s: s
        mock_ddgs.return_value.__exit__ = lambda s, *a: None
        mock_ddgs.return_value.text.return_value = [
            {"title": "Example", "href": "https://example.com", "body": "A domain"}
        ]

        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_instance.get.return_value = mock_response

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


def test_status_endpoint() -> None:
    server = MCPServer()
    client = TestClient(server.app)
    resp = client.get("/status")
    assert resp.status_code == 200
    assert "pipelines" in resp.json()


def test_kb_roundtrip() -> None:
    server = MCPServer()
    client = TestClient(server.app)

    # Add a document
    payload = {"id": "test-doc-1", "text": "hello world from mcp", "metadata": {}}
    resp = client.post("/kb/add", json=payload)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Search for it
    resp = client.get("/kb/search", params={"q": "hello world", "k": 3})
    assert resp.status_code == 200
    assert any("hello world" in r["text"] for r in resp.json()["results"])
