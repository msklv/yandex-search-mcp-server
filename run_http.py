"""HTTP entrypoint for the official Yandex Search MCP server.

The upstream `server.py` runs ONLY over stdio (mcp.run(transport="stdio")).
This thin wrapper re-exports its FastMCP instance and serves it over
StreamableHTTP so it can live in a Docker Compose stack as an
HTTP-MCP (matching mcp-atlassian / github-mcp).

Usage: uvicorn-less, self-contained:
    python run_http.py
Env:
    YANDEX_MCP_HOST  (default 0.0.0.0)
    YANDEX_MCP_PORT  (default 8766)
Exposes the StreamableHTTP endpoint at /mcp by default.
"""
import os
from server import mcp  # the upstream FastMCP instance (no upstream file is edited)

mcp.settings.host = os.getenv("YANDEX_MCP_HOST", "0.0.0.0")
mcp.settings.port = int(os.getenv("YANDEX_MCP_PORT", "8766"))

if __name__ == "__main__":
    mcp.run(transport="streamable-http")