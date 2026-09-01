# Changelog

All notable changes to this project follow [Semantic Versioning](https://semver.org/).
Releases are tagged `v<major>.<minor>.<patch>` and published to GHCR
(`ghcr.io/msklv/yandex-search-mcp-server:v<version>`).

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