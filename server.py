"""
Yandex Search API MCP Server — all search types.

Exposes every type of the Yandex Search API v2 over MCP:

- ``web_search``             text search, sync  (returns parsed results)
- ``web_search_async``       text search, deferred -> Operation, poll with ``get_operation``
- ``get_operation``         fetch a deferred search Operation
- ``gen_search``            generative answer (YandexGPT) — requires FOLDER_ID
- ``image_search``          search images by text description
- ``image_search_by_image``  search images by a given image (url / data / id)

Russian is the default search type (SEARCH_TYPE_RU, LOCALIZATION_RU, region 225 = Россия).

Modified from yandex/yandex-search-mcp-server (c) 2025 YANDEX LLC, Apache-2.0.
Changes: expanded to all search types. Not an official Yandex product.
"""
import json

from mcp.server.fastmcp import FastMCP
from detail import (
    call_gen_search,
    call_image_search,
    call_search_by_image,
    call_web_search,
    call_web_search_async,
    extract_documents_from_xml,
    get_operation,
    _doc_elements,
)

mcp = FastMCP(name="Yandex Search Api v2 (all search types)")


def _run(fn, body):
    """Run a detail call, returning a JSON string on success or {'error': ...}."""
    try:
        result = fn(body)
    except Exception as exc:  # surface validation / auth / HTTP errors to the agent
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def web_search(body: dict) -> str:
    """Search the web via Yandex Search API v2 (sync, XML). Russian by default.

    Args:
        body (dict): input containing:
            - query: required. Search query string (Russian supported natively).
            - search_region: optional. 'ru' (default) | 'tr' | 'com' | 'kk' | 'be' | 'uz'.
            - region: optional. Numeric Yandex region id, only for 'ru'/'tr' (213 = Москва).
            - limit: optional. Groups per page, 1..20 (default 5).
    Returns:
        str: JSON {"responses": [{"data", "source"}], ...} + "count".
    """
    try:
        xml = call_web_search(body)
        responses = []
        for doc in extract_documents_from_xml(xml):
            rec = _doc_elements(doc)
            url = rec.get("url")
            if not url:
                continue
            title = rec.get("headline") or rec.get("title") or rec.get("passage") or ""
            responses.append({"data": title, "source": url})
        return json.dumps({"responses": responses, "count": len(responses)}, ensure_ascii=False, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@mcp.tool()
def web_search_async(body: dict) -> str:
    """Start a deferred (async) text search via Yandex Search API v2.

    Returns an Operation object with an ``id``. Poll with ``get_operation`` until
    it is ``done``, then the result is in ``response.rawData`` (base64 XML).

    Args:
        body (dict): same as ``web_search`` (query / search_region / region / limit).
    Returns:
        str: JSON operation object ({"id": ..., "done": false, ...}).
    """
    return _run(call_web_search_async, body)


@mcp.tool()
def get_operation(operation_id: str) -> str:
    """Poll a deferred search Operation by its id (from ``web_search_async``).

    Args:
        operation_id (str): the Operation id returned by ``web_search_async``.
    Returns:
        str: JSON Operation. When done, ``response.rawData`` holds base64-encoded
             XML search results.
    """
    try:
        return json.dumps(get_operation(operation_id), ensure_ascii=False, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


@mcp.tool()
def gen_search(body: dict) -> str:
    """Generative search: web search + a concise answer synthesized by YandexGPT.

    Requires FOLDER_ID (env). Sync only, max 1 req/sec.

    Args:
        body (dict):
            - query: required. The question (or pass ``messages`` list of
              {"role": "ROLE_USER"|"ROLE_ASSISTANT", "content": ...} for chat context).
            - search_region: optional, default 'ru'.
            - site | host | url: optional, restrict search scope (mutually exclusive).
            - fix_misspell: optional bool. Correct query misspellings.
            - enable_rich_structured_answer: optional bool.
            - get_partial_results: optional bool. Stream partial JSON-Lines results.
    Returns:
        str: JSON response with {message: {content}, sources: [...], hints, ...}.
    """
    return _run(call_gen_search, body)


@mcp.tool()
def image_search(body: dict) -> str:
    """Search images by a text description via Yandex Search API v2 (synconly).

    Args:
        body (dict):
            - query: required. Text description of the images to find.
            - search_region: optional, default 'ru'.
            - size / orientation / color / format: optional image filters
              (IMAGE_SIZE_LARGE, IMAGE_ORIENTATION_SQUARE, IMAGE_COLOR_RED, IMAGE_FORMAT_PNG ...).
            - docs_on_page: optional int 1..100.
            - site: optional str, restrict to a website.
    Returns:
        str: JSON {"images": [{"url", "title", "width", "height", ...}], "count": N}.
    """
    return _run(call_image_search, body)


@mcp.tool()
def image_search_by_image(body: dict) -> str:
    """Search images by a given image (synconly). Provide exactly one of:

    Args:
        body (dict):
            - url:  the image URL to search by (optional).
            - data: base64-encoded image data (optional; max ~3 MB).
            - id:   CBIR image id (optional).
            - site: optional, restrict to a website.
            - page: optional int.
    Returns:
        str: JSON {"images": [{"url", "pageTitle", "pageUrl", "width", ...}], ...}.
    """
    return _run(call_search_by_image, body)


if __name__ == "__main__":
    mcp.run(transport="stdio")