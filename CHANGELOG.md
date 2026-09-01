# Changelog

All notable changes to this project follow [Semantic Versioning](https://semver.org/).
Releases are tagged `v<major>.<minor>.<patch>` and published to GHCR
(`ghcr.io/msklv/yandex-search-mcp-server:v<version>`).

## [1.3.0] - 2026-09-01

### Added
- Multi-architecture Docker image: `linux/amd64` + `linux/arm64` (Apple Silicon / M-series).

### Changed
- Dockerfile OCI label `org.opencontainers.image.version` → `1.3.0`.

## [1.2.0] - 2026-09-01

### Fixed
- Reverted `mcp` to `1.29.1`. `mcp 2.x` renamed `FastMCP`→`MCPServer` and removed
  `mcp.server.fastmcp`, breaking the server; the Dependabot bump had also desynced
  `requirements.txt` (`2.1.1`) from the Dockerfile (`1.29.1`).
- `get_operation` tool: fixed infinite recursion — the tool name shadowed the imported
  `detail.get_operation`; now imported as `_get_operation`.

### Added
- Unit tests (`tests/`): request building, XML parsing, mocked-HTTP calls and MCP tool
  contracts for all search types (`test_detail.py`, `test_server.py`).

### Changed
- Dockerfile OCI label `org.opencontainers.image.version` → `1.2.0`.

## [1.1.0] - 2026-09-01

### Security
- Added CI security pipeline: CodeQL (static analysis), Trivy (CVE fs-scan),
  pip-audit (Python advisories) and Dependabot (weekly `pip` / `github-actions`).
- `requests` bumped `2.31.0` → `2.34.2` to close PYSEC-2026-1873 / 1872 / 2275.

## [1.0.0] - 2026-09-01

Initial release: StreamableHTTP MCP server for all Yandex Search API v2 search types.

### Added
- `web_search` — text search, synchronous (parsed `{responses:[{data,source}], count}`).
- `web_search_async` — text search, deferred; returns an Operation to poll.
- `get_operation` — poll a deferred search Operation.
- `gen_search` — generative answer (YandexGPT); requires `FOLDER_ID`.
- `image_search` — search images by a text description.
- `image_search_by_image` — search images by a given image (`url`/`data`/`id`).
- GitHub Actions → builds and pushes the image to GHCR (`latest`, `main`, `vN.N.N`, `sha-*`).
- Chinese-style `ensure_ascii=False` JSON output; Russian default
  (`SEARCH_TYPE_RU`, `LOCALIZATION_RU`, region `225`).
- Fork of [`yandex/yandex-search-mcp-server`](https://github.com/yandex/yandex-search-mcp-server),
  Apache-2.0, © 2025 YANDEX LLC.