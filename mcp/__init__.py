"""Shared MCP server with pipeline registry and web tooling.

Use `MCPServer` directly in Python, or serve via `uvicorn mcp.server:create_app --factory`.
See `mcp/README.md` for endpoints and quick-start.
"""

from .server import MCPServer

__all__ = ["MCPServer"]
