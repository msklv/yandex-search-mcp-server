# Yandex Search API MCP server — StreamableHTTP build

Self-hostable [Model Context Protocol](https://modelcontextprotocol.io) server for the
[Yandex Search API v2](https://aistudio.yandex.ru/ru/docs/search-api/) — **web search only**,
served over **StreamableHTTP** (`/mcp`) so it can run as an HTTP-MCP backend in a Docker/Compose
stack (alongside other HTTP-MCP servers).

This is a fork of the official
[`yandex/yandex-search-mcp-server`](https://github.com/yandex/yandex-search-mcp-server)
(which exposes only stdio and always includes the AI/Yazeka endpoint). **Not an official Yandex
product and not endorsed by Yandex.** Two deviations:

1. **HTTP transport** — adds `run_http.py`, which re-exports the same FastMCP instance and serves
   it over StreamableHTTP, so the container behaves like any HTTP-MCP service.
2. **Search only** — the AI/generative (`yazeka`) endpoint is intentionally **not** exposed; only
   `web_search`. Russian is the default search type (`SEARCH_TYPE_RU`, `LOCALIZATION_RU`,
   region `225` = Россия).

> ⚠️ Derivative work. Files inherited from upstream (`server.py`, `detail.py`) are © 2025
> **YANDEX LLC**, Apache-2.0. See [LICENSE](./LICENSE).

## Tools

All search types of the Yandex Search API v2 are exposed. Russian is the default
(`SEARCH_TYPE_RU`, `LOCALIZATION_RU`, region `225` = Россия).

| Tool | Search type | Mode | Response |
|---|---|---|---|
| `web_search` | Текстовый (web pages) | sync | parsed `{responses:[{data,source}], count}` |
| `web_search_async` | Текстовый (web pages) | **deferred** | Operation `{id}` → poll with `get_operation` |
| `get_operation` | — | — | Operation status + base64 `response.rawData` when `done` |
| `gen_search` | Генеративный ответ (YandexGPT) | sync | JSON answer + `sources[]` + `hints[]` |
| `image_search` | Поиск изображений по тексту | sync | `{images:[{url,title,width,height,…}], count}` |
| `image_search_by_image` | Поиск изображений по изображению | sync | `{images:[…], page, id}` |

> `gen_search` requires the `FOLDER_ID` env var (the Yandex folder the key belongs to).

Docs (search types & modes): <https://aistudio.yandex.ru/ru/docs/search-api/concepts/>

## Container image (GHCR)

Every push to `main` (and every `v*` tag) builds and publishes the image to the
**GitHub Container Registry**:

```
ghcr.io/msklv/yandex-search-mcp-http:latest     # default branch
ghcr.io/msklv/yandex-search-mcp-http:main       # branch ref
ghcr.io/msklv/yandex-search-mcp-http:v<tag>     # semver tag
```

The container serves the MCP server over StreamableHTTP on port `8766`:

```bash
docker run --rm -p 8766:8766 \
  -e SEARCH_API_KEY=... [-e FOLDER_ID=...] \
  ghcr.io/msklv/yandex-search-mcp-http:latest
# MCP endpoint: http://<host>:8766/mcp
```

## Requirements

- Python 3.10+ / Docker 20+.
- A [Yandex Search API](https://aistudio.yandex.ru/ru/docs/search-api/) key (and optionally a
  folder id). Credentials come from env vars at runtime — the repository contains **no** secrets.

| Env var | Required | Notes |
|---|---|---|
| `SEARCH_API_KEY` | ✅ | Yandex Search API key (`Authorization: Api-Key *`). |
| `FOLDER_ID` | ⚠️ optional | Yandex Cloud folder id; accepted but not mandatory for service-account keys. |
| `YANDEX_MCP_HOST` | no | HTTP bind host, default `0.0.0.0`. |
| `YANDEX_MCP_PORT` | no | HTTP port, default `8766`. |

## Run

```bash
# local, stdio (upstream behaviour)
export SEARCH_API_KEY=...
python3 server.py

# local, StreamableHTTP on 8766 (/mcp)
export SEARCH_API_KEY=...
python3 run_http.py

# docker
docker build -t yandex-search-mcp-http .
docker run --rm -p 8766:8766 \
  -e SEARCH_API_KEY=... [-e FOLDER_ID=...] \
  yandex-search-mcp-http
```

## web_search

```python
await mcp.call_tool("web_search", {"body": {"query": "кофемашина", "region": 213}})
```

- `query` (required) — search query; Cyrillic supported natively.
- `search_region` (optional) — `ru` (default) / `tr` / `com` / `kk` / `be` / `uz`.
- `region` (optional) — numeric Yandex region id to bias ranking (only `ru`/`tr`);
  default `225` (Россия) for `ru`, e.g. `213` = Москва, `2` = Санкт-Петербург.

## License

Apache-2.0. Original copyright on derived files: **2025 YANDEX LLC**.
This fork's additions (`run_http.py`, HTTP Dockerfile, this README) by **msklv**, Apache-2.0.