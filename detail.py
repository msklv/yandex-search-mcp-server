"""Yandex Search API v2 — HTTP call implementation (REST).

Covers all search types of the Search API:
- WebSearch.Search        (sync,  ``POST /v2/web/search``)
- WebSearch.SearchAsync   (deferred, ``POST /v2/web/searchAsync`` + ``GET /v2/operations/{id}``)
- GenSearch.Search       (generative answer via YandexGPT, ``POST /v2/gen/search``)
- ImageSearch.Search     (images by text, ``POST /v2/image/search``)
- ImageSearch.SearchByImage (images by image, ``POST /v2/image/search_by_image``)

Credentials are read from the environment at call time (never hard-coded / committed):
- ``SEARCH_API_KEY`` — required for every call.
- ``FOLDER_ID``      — optional for Web/Image searches; **required** for GenSearch.

REST uses camelCase in the request body; all fields of a response are optional.

Modified from yandex/yandex-search-mcp-server (c) 2025 YANDEX LLC, Apache-2.0.
Changes: expanded to all search types, region-aware defaults for Russian/Turkish.
Not an official Yandex product.
"""
import base64
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

API_BASE = "https://searchapi.api.cloud.yandex.net/v2"
DEFAULT_TIMEOUT = 20


def _search_type(data: Dict[str, Any]) -> Tuple[str, str, str]:
    """Return (search_type, l10n) for the human `search_region` code (default 'ru').

    codes: ru/tr/com/kk/be/uz. l10n is the notification language of the response.
    """
    mapping = {
        "ru": ("SEARCH_TYPE_RU", "LOCALIZATION_RU"),
        "tr": ("SEARCH_TYPE_TR", "LOCALIZATION_TR"),
        "com": ("SEARCH_TYPE_COM", "LOCALIZATION_EN"),
        "kk": ("SEARCH_TYPE_KK", "LOCALIZATION_KK"),
        "be": ("SEARCH_TYPE_BE", "LOCALIZATION_BE"),
        "uz": ("SEARCH_TYPE_UZ", "LOCALIZATION_UZ"),
    }
    code = str(data.get("search_region", "ru")).lower()
    if code not in mapping:
        raise ValueError(
            "Invalid search_region: %r. Allowed: %s" % (code, ", ".join(sorted(mapping)))
        )
    return mapping[code]


def _maybe_region(data: Dict[str, Any], search_type: str) -> Optional[int]:
    """Numeric Yandex region id for ranking; only 'ru'/'tr' accept it. Default 225 (Россия)."""
    if search_type == "SEARCH_TYPE_RU":
        default_region = 225
    elif search_type == "SEARCH_TYPE_TR":
        default_region = None
    else:
        return None
    raw = data.get("region")
    if raw is None:
        return default_region if default_region is not None else None
    try:
        region_id = int(raw)
    except (ValueError, TypeError):
        raise ValueError("Invalid region: %r. Region must be numeric (e.g. 213 = Москва)." % (raw,))
    return region_id


def _web_query(data: Dict[str, Any]) -> Dict[str, Any]:
    search_type, l10n = _search_type(data)
    query: Dict[str, Any] = {
        "searchType": search_type,
        "queryText": data["query"],
        # fixTypoMode ON by default: essential for Russian queries.
        "fixTypoMode": data.get("fix_typo_mode", "FIX_TYPO_MODE_ON"),
        "familyMode": data.get("family_mode", "FAMILY_MODE_NONE"),
    }
    region_id = _maybe_region(data, search_type)
    if region_id is not None:
        query["region"] = region_id
    return query


def _folder_id() -> str:
    return os.getenv("FOLDER_ID") or os.getenv("YANDEX_SEARCH_FOLDER_ID") or ""


def _api_key() -> str:
    key = os.getenv("SEARCH_API_KEY") or os.getenv("YANDEX_SEARCH_API_KEY")
    if not key:
        raise ValueError("SEARCH_API_KEY environment variable not set")
    return key


def _headers() -> Dict[str, str]:
    return {"Content-Type": "application/json", "Authorization": f"Api-Key {_api_key()}"}


def _clean(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"</?hlword>", "", text).strip()


def make_http_request(url: str, json_body: Dict[str, Any], decode_base64: bool = False) -> str:
    with requests.post(url, json=json_body, headers=_headers(), timeout=DEFAULT_TIMEOUT) as resp:
        resp.raise_for_status()
        if decode_base64:
            return base64.b64decode(json.loads(resp.text)["rawData"]).decode("utf-8")
        return resp.text


def call_web_search(data: Dict[str, Any]) -> str:
    """Synchronous text search -> decoded XML response string."""
    body = {
        "query": _web_query(data),
        "groupSpec": {"groupsOnPage": max(1, min(int(data.get("limit", 5)), 20))},
        "l10n": _search_type(data)[1],
        "responseFormat": "FORMAT_XML",
    }
    folder_id = _folder_id()
    if folder_id:
        body["folderId"] = folder_id
    return make_http_request(f"{API_BASE}/web/search", body, decode_base64=True)


def call_web_search_async(data: Dict[str, Any]) -> dict:
    """Start a deferred (async) text search -> Operation object ({id}, ...).

    The caller then polls the result with ``get_operation(operation_id)``.
    """
    body = {
        "query": _web_query(data),
        "groupSpec": {"groupsOnPage": max(1, min(int(data.get("limit", 5)), 20))},
        "l10n": _search_type(data)[1],
        "responseFormat": "FORMAT_XML",
    }
    folder_id = _folder_id()
    if folder_id:
        body["folderId"] = folder_id
    return json.loads(make_http_request(f"{API_BASE}/web/searchAsync", body))


def get_operation(operation_id: str) -> dict:
    """Fetch an Operation created by a deferred search (e.g. ``web_search_async``).

    When ``done`` is true the result is available under ``response``
    (a ``WebSearchResponse`` whose ``rawData`` is base64-encoded XML).
    """
    with requests.get(
        f"{API_BASE}/operations/{operation_id}", headers=_headers(), timeout=DEFAULT_TIMEOUT
    ) as resp:
        resp.raise_for_status()
        return resp.json()


def call_gen_search(data: Dict[str, Any]) -> dict:
    """Generative answer (YandexGPT). Requires FOLDER_ID. Sync only.

    Body is a real JSON object (not base64). With ``get_partial_results`` the service
    streams JSON Lines; we default to the single final object.
    """
    messages = data.get("messages")
    if not messages:
        messages = [{"role": "ROLE_USER", "content": data.get("query")}]
    body: Dict[str, Any] = {"messages": messages, "folderId": _folder_id()}
    if not body["folderId"]:
        raise ValueError("FOLDER_ID environment variable is required for generative search")

    body["searchType"], _ = _search_type(data)
    for opt in ("site", "host", "url"):
        if data.get(opt):
            body[opt] = {opt: data[opt] if isinstance(data[opt], list) else [data[opt]]}
            break
    if data.get("fix_misspell") is not None:
        body["fixMisspell"] = bool(data["fix_misspell"])
    if data.get("enable_rich_structured_answer") is not None:
        body["enableRichStructuredAnswer"] = bool(data["enable_rich_structured_answer"])
    if data.get("search_filters"):
        body["searchFilters"] = data["search_filters"]
    if data.get("get_partial_results"):
        body["getPartialResults"] = True
        raw = make_http_request(f"{API_BASE}/gen/search", body)
        lines = [json.loads(ln) for ln in raw.strip().splitlines() if ln.strip()]
        return {"partial": lines}
    return json.loads(make_http_request(f"{API_BASE}/gen/search", body))


# ---------------------------------------------------------------------------
# Image search helpers (XML response from ImageSearch.Search is parsed into records)
# ---------------------------------------------------------------------------


def extract_documents_from_xml(xml_content: str) -> List[str]:
    """Split the response XML into individual ``<doc>`` blocks (lossy but robust)."""
    doc_strings, current, in_doc = [], [], False
    for line in xml_content.split("\n"):
        if not in_doc and "<doc " in line and "id=" in line:
            in_doc, current = True, [line]
        elif in_doc and "</doc>" in line:
            current.append(line)
            doc_strings.append("\n".join(current))
            in_doc = False
        elif in_doc:
            current.append(line)
    return doc_strings


def clean_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    return re.sub(r"<hlword>|</hlword>", "", text).strip() or None


_IMG_FIELDS = ("url", "title", "headline", "width", "height", "format", "host", "pageUrl", "passage")


def _doc_elements(doc: str) -> Dict[str, Optional[str]]:
    result: Dict[str, Optional[str]] = {}
    for name in _IMG_FIELDS:
        m = re.search(rf"<{name}>(.*?)</{name}>", doc, re.S)
        result[name] = clean_text(m.group(1)) if m else None
    passages = re.findall(r"<passage>(.*?)</passage>", doc, re.S)
    if not result.get("passage") and passages:
        result["passage"] = clean_text(passages[0])
    return result


def call_image_search(data: Dict[str, Any]) -> Dict[str, Any]:
    """Search images by a text description -> list of parsed image records + total count."""
    body: Dict[str, Any] = {"query": _web_query(data)}
    folder_id = _folder_id()
    if folder_id:
        body["folderId"] = folder_id
    spec: Dict[str, Any] = {}
    for k in ("format", "size", "orientation", "color"):
        if data.get(k.lower()):
            spec[k] = data[k.lower()]
    if spec:
        body["imageSpec"] = spec
    if data.get("docs_on_page"):
        body["docsOnPage"] = int(data["docs_on_page"])
    if data.get("site"):
        body["site"] = data["site"]

    xml = make_http_request(f"{API_BASE}/image/search", body, decode_base64=True)
    images = []
    for doc in extract_documents_from_xml(xml):
        rec = _doc_elements(doc)
        url = rec.get("url")
        if not url:
            continue
        rec.pop("headline", None)
        title = rec.get("title") or rec.pop("passage", None) or ""
        rec["title"] = title
        images.append({k: v for k, v in rec.items() if v is not None})
    return {"images": images, "count": len(images)}


def call_search_by_image(data: Dict[str, Any]) -> dict:
    """Search images by a given image (one of ``url`` / ``data`` / ``id``). Returns JSON."""
    body_keys = [k for k in ("url", "data", "id") if data.get(k)]
    if not body_keys:
        raise ValueError("search_by_image requires one of: url, data, id")
    body: Dict[str, Any] = {body_keys[0]: data[body_keys[0]]}
    folder_id = _folder_id()
    if folder_id:
        body["folderId"] = folder_id
    if data.get("site"):
        body["site"] = data["site"]
    if data.get("page") is not None:
        body["page"] = int(data["page"])
    if data.get("family_mode"):
        body["familyMode"] = data["family_mode"]
    return json.loads(make_http_request(f"{API_BASE}/image/search_by_image", body))