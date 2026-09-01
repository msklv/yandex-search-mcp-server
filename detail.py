import os
import json
import base64
from typing import Any, Dict, Optional, Tuple

import requests
from requests.exceptions import RequestException

# API Configuration — only web search (AI/generative search is intentionally NOT used).
# Modified from yandex/yandex-search-mcp-server (c) 2025 YANDEX LLC, Apache-2.0.
# Changes: web-search only, region-aware defaults for Russian/Turkish. Not an official Yandex product.
WEB_SEARCH_URL = "https://searchapi.api.cloud.yandex.net/v2/web/search"
DEFAULT_TIMEOUT = 30

# Default region ids (reference/regions):
#   225 — Россия, 213 — Москва, 2 — Санкт-Петербург, 149 — Беларусь, 159 — Казахстан.
DEFAULT_REGION_RU = 225

# Map of search-type codes -> (SEARCH_TYPE_*, LOCALIZATION_*). Russian is the default.
SEARCH_TYPES = {
    "ru": ("SEARCH_TYPE_RU", "LOCALIZATION_RU"),
    "tr": ("SEARCH_TYPE_TR", "LOCALIZATION_TR"),
    "com": ("SEARCH_TYPE_COM", "LOCALIZATION_EN"),
    "kk": ("SEARCH_TYPE_KK", "LOCALIZATION_KK"),
    "be": ("SEARCH_TYPE_BE", "LOCALIZATION_BE"),
    "uz": ("SEARCH_TYPE_UZ", "LOCALIZATION_UZ"),
}
DEFAULT_SEARCH_TYPE = "ru"

# Only RU and TR types accept a numeric region at all.
REGION_CAPABLE_TYPES = {"ru", "tr"}
# Type-independent, default region id used when none is given for a region-capable type.
DEFAULT_REGIONS = {"ru": DEFAULT_REGION_RU}


def resolve_search(data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[int]]:
    """Resolve (search_type, l10n, region_id) from the request body.

    `search_region` (default 'ru') selects the search type:
        'ru'  — Russian (SEARCH_TYPE_RU, LOCALIZATION_RU)
        'tr'  — Turkish
        'com' — International
        'kk'  — Kazakh, 'be' — Belarusian, 'uz' — Uzbek
    `region` (optional) — numeric Yandex region id to bias ranking (only for 'ru'/'tr').
        Defaults to 225 (Россия) for 'ru'.
    Returns an error string instead on invalid input.
    """
    search_code = data.get("search_region", DEFAULT_SEARCH_TYPE)
    search_code = str(search_code).lower()

    if search_code not in SEARCH_TYPES:
        error = "Invalid search_region: %r. Allowed: %s" % (
            search_code,
            ", ".join(sorted(SEARCH_TYPES)),
        )
        return error, None, None

    search_type, l10n = SEARCH_TYPES[search_code]

    region_id = None
    raw_region = data.get("region")
    if raw_region is not None:
        try:
            region_id = int(raw_region)
        except (ValueError, TypeError):
            return (
                "Invalid region: %r. Region must be a numeric Yandex region id "
                "(e.g. 225 = Россия, 213 = Москва)." % (raw_region,)
            ), None, None
        if search_code not in REGION_CAPABLE_TYPES:
            return (
                "Region is only supported for search types 'ru' and 'tr', got %r." % (search_code,)
            ), None, None
    elif search_code in DEFAULT_REGIONS:
        region_id = DEFAULT_REGIONS[search_code]

    return search_type, l10n, region_id


def make_http_request(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    decode_base64: bool = False,
) -> str:
    try:
        with requests.post(url, headers=headers, json=json_body, timeout=timeout) as response:
            response.raise_for_status()

            if decode_base64:
                decoded_data = base64.b64decode(json.loads(response.text)["rawData"]).decode("utf-8")
                return decoded_data
            return response.text

    except RequestException as e:
        raise RuntimeError(f"API request failed: {str(e)}") from e


def validate_input_data(data: Dict[str, Any], required_keys: set) -> Optional[str]:
    if missing_keys := required_keys - set(data):
        return f"Missing required keys: {', '.join(sorted(missing_keys))}"
    return None


def call_web_search(data: Dict[str, Any]) -> str:
    api_key = os.getenv("SEARCH_API_KEY")
    folder_id = os.getenv("FOLDER_ID")
    if not api_key:
        raise ValueError("SEARCH_API_KEY environment variable not set")

    search_type, l10n, region_id = resolve_search(data)
    if search_type is None:
        raise ValueError(search_type)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Api-Key {api_key}",
    }

    query = {
        "searchType": search_type,
        "queryText": data["query"],
        # fixTypoMode ON by default: essential for Russian queries (typos / wrong layout).
        "fixTypoMode": "FIX_TYPO_MODE_ON",
        "familyMode": "FAMILY_MODE_NONE",
    }
    if region_id is not None:
        query["region"] = region_id

    body = {
        "query": query,
        "folderId": folder_id,
        "groupSpec": {"groupsOnPage": 4},
        "l10n": l10n,
        "responseFormat": "FORMAT_XML",
    }

    return make_http_request(WEB_SEARCH_URL, headers=headers, json_body=body, timeout=10, decode_base64=True)