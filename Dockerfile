# Yandex Search API MCP server — self-host build for a Docker Compose MCP stack.
#
# The upstream repo (github.com/yandex/yandex-search-mcp-server) publishes NO
# image to a registry — only a Dockerfile + source. So this stack builds it
# locally (a documented exception to the "pull images from registry" rule).
#
# Two deviations from upstream:
#   1. transport: upstream runs ONLY stdio. We add run_http.py, which re-exports
#      the same FastMCP instance and serves it over StreamableHTTP (HTTP-MCP), so
#      it matches mcp-atlassian/github-mcp in this compose.
#   2. mcp is pinned <2 : the upstream requirements.txt (mcp[cli]==0.1.0) is
#      stale, and mcp 2.x renamed FastMCP→MCPServer and broke the API this
#      server uses. mcp[cli]==1.29.1 still ships FastMCP + uvicorn for
#      streamable-http (verified working).
FROM python:3.10-slim

LABEL org.opencontainers.image.title="Yandex Search API MCP Server (HTTP)"
LABEL org.opencontainers.image.description="MCP server for Yandex Search API v2 served over StreamableHTTP"
LABEL org.opencontainers.image.vendor="Yandex LLC + HTTP-MCP wrapper"
LABEL org.opencontainers.image.version="1.0.0"

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# requests pinned; mcp[cli] pinned to a FastMCP-compatible <2 line.
RUN pip install --no-cache-dir --no-input 'requests==2.34.2' 'mcp[cli]==1.29.1'

COPY server.py detail.py run_http.py ./

EXPOSE 8766

# liveness: confirm the port is accepting connections (GET /mcp returns 406 by
# design on streamable-http, so a TCP connect is the correct readiness check).
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=5 \
  CMD python3 -c "import socket,sys; socket.create_connection(('127.0.0.1',8766),3)" || exit 1

CMD ["python3", "run_http.py"]