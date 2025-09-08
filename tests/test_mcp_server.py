"""Tests for the shared MCP server."""

from __future__ import annotations

from typing import Dict

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
