"""Unit tests for the pure request-building / parsing logic and the HTTP call layer.

No network: ``requests.post`` / ``requests.get`` are monkeypatched. Uses the same
XML shape the Yandex Search API returns.
"""
import base64
import json

import pytest

import detail

SAMPLE_XML = """<response>
<doc id="1">
<url>https://example.com/1</url>
<title>Кофе</title>
<headline>Лучшая <hlword>2026</hlword> кофемашина</headline>
</doc>
<doc id="2">
<url>https://example.com/2</url>
<passage>про кофе</passage>
</doc>
<doc id="3">
<headline>без ссылки</headline>
</doc>
</response>"""


class FakeResp:
    """Context-manager response; captures the request that produced it."""

    def __init__(self, text, json_body=None):
        self.text = text
        self._json = json.loads(text) if json_body is None else None
        self.json_body = json_body  # the json= kwarg sent to requests.post

    def raise_for_status(self):
        pass

    def json(self):
        return self._json

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _watch(monkeypatch, method, factory):
    """Monkeypatch detail.requests.<method>, record (url, kwargs, FakeResp)."""
    calls = []

    def fake(url, **kw):
        calls.append((url, kw))
        return factory(url, kw)

    monkeypatch.setattr(detail.requests, method, fake)
    return calls


def _b64_xml(xml):
    return json.dumps({"rawData": base64.b64encode(xml.encode()).decode()})


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("SEARCH_API_KEY", "test-key")


# --- search type / region / query -------------------------------------------------
def test_search_type_defaults_to_ru():
    assert detail._search_type({}) == ("SEARCH_TYPE_RU", "LOCALIZATION_RU")


def test_search_type_all_codes():
    assert detail._search_type({"search_region": "tr"})[0] == "SEARCH_TYPE_TR"
    assert detail._search_type({"search_region": "com"})[0] == "SEARCH_TYPE_COM"
    assert detail._search_type({"search_region": "kk"}) == ("SEARCH_TYPE_KK", "LOCALIZATION_KK")


def test_search_type_invalid_raises():
    with pytest.raises(ValueError):
        detail._search_type({"search_region": "xx"})


def test_region_ru_defaults_225():
    assert detail._maybe_region({}, "SEARCH_TYPE_RU") == 225


def test_region_ru_explicit():
    assert detail._maybe_region({"region": 213}, "SEARCH_TYPE_RU") == 213


def test_region_tr_has_no_default_but_accepts_value():
    assert detail._maybe_region({}, "SEARCH_TYPE_TR") is None
    assert detail._maybe_region({"region": 34}, "SEARCH_TYPE_TR") == 34


def test_region_ignored_for_com():
    assert detail._maybe_region({"region": 99}, "SEARCH_TYPE_COM") is None


def test_region_invalid_raises():
    with pytest.raises(ValueError):
        detail._maybe_region({"region": "abc"}, "SEARCH_TYPE_RU")


def test_web_query_builds_ru_defaults():
    q = detail._web_query({"query": "кофе"})
    assert q["searchType"] == "SEARCH_TYPE_RU"
    assert q["queryText"] == "кофе"
    assert q["region"] == 225
    assert q["fixTypoMode"] == "FIX_TYPO_MODE_ON"
    assert q["familyMode"] == "FAMILY_MODE_NONE"


def test_web_query_com_omits_region():
    q = detail._web_query({"query": "x", "search_region": "com"})
    assert "region" not in q


def test_web_query_custom_flags():
    q = detail._web_query(
        {"query": "x", "search_region": "tr", "region": 34,
         "fix_typo_mode": "FIX_TYPO_MODE_OFF",
         "family_mode": "FAMILY_MODE_MODERATE"}
    )
    assert q["region"] == 34
    assert q["fixTypoMode"] == "FIX_TYPO_MODE_OFF"
    assert q["familyMode"] == "FAMILY_MODE_MODERATE"


# --- XML parsing -----------------------------------------------------------------
def test_extract_documents_from_xml_splits_docs():
    docs = detail.extract_documents_from_xml(SAMPLE_XML)
    assert len(docs) == 3
    assert "https://example.com/1" in docs[0]


def test_clean_text_strips_hlword():
    assert detail.clean_text("<hlword>к</hlword>офе") == "кофе"
    assert detail.clean_text(None) is None
    assert detail.clean_text("   ") is None


def test_doc_elements_extracts_and_cleans():
    rec = detail._doc_elements(
        '<doc id="1"><url>https://example.com/1</url>'
        "<title>Кофе</title><headline>Лучшая <hlword>2026</hlword> кофемашина</headline></doc>"
    )
    assert rec["url"] == "https://example.com/1"
    assert rec["title"] == "Кофе"
    assert rec["headline"] == "Лучшая 2026 кофемашина"


def test_doc_elements_passage_fallback():
    rec = detail._doc_elements(
        '<doc id="2"><url>https://example.com/2</url><passage>про кофе</passage></doc>'
    )
    assert rec["passage"] == "про кофе"


# --- web search (HTTP mocked) -----------------------------------------------------
def test_call_web_search_parses_and_limits(monkeypatch, api_key):
    monkeypatch.setenv("FOLDER_ID", "folder-1")
    calls = _watch(
        monkeypatch, "post",
        lambda url, kw: FakeResp(_b64_xml(SAMPLE_XML), kw),
    )
    out = detail.call_web_search({"query": "кофе", "limit": 50})  # 50 -> clamp 20
    assert "https://example.com/1" in out
    url, kw = calls[0]
    assert url == f"{detail.API_BASE}/web/search"
    body = kw["json"]
    assert body["groupSpec"]["groupsOnPage"] == 20
    assert body["query"]["region"] == 225
    assert body["folderId"] == "folder-1"


def test_call_web_search_no_folder_id(monkeypatch, api_key):
    monkeypatch.delenv("FOLDER_ID", raising=False)
    monkeypatch.delenv("YANDEX_SEARCH_FOLDER_ID", raising=False)
    calls = _watch(monkeypatch, "post", lambda url, kw: FakeResp(_b64_xml(SAMPLE_XML), kw))
    detail.call_web_search({"query": "x"})
    assert "folderId" not in calls[0][1]["json"]


def test_call_web_search_requires_key(monkeypatch):
    monkeypatch.delenv("SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("YANDEX_SEARCH_API_KEY", raising=False)
    with pytest.raises(ValueError):
        detail.call_web_search({"query": "x"})


def test_call_web_search_async_returns_operation(monkeypatch, api_key):
    monkeypatch.setenv("FOLDER_ID", "f")
    calls = _watch(
        monkeypatch, "post",
        lambda url, kw: FakeResp(json.dumps({"id": "op-1", "done": False}), kw),
    )
    out = detail.call_web_search_async({"query": "x", "limit": 0})  # 0 -> clamp 1
    assert out == {"id": "op-1", "done": False}
    assert calls[0][0].endswith("/web/searchAsync")
    assert calls[0][1]["json"]["groupSpec"]["groupsOnPage"] == 1


def test_get_operation(monkeypatch, api_key):
    monkeypatch.delenv("OPERATION_API_BASE", raising=False)
    calls = _watch(
        monkeypatch, "get",
        lambda url, kw: FakeResp(json.dumps({"id": "o", "done": True})),
    )
    assert detail.get_operation("o")["done"] is True
    assert calls[0][0] == "https://operation.api.cloud.yandex.net/operations/o"


def test_get_operation_honors_operation_api_base_override(monkeypatch, api_key):
    monkeypatch.setenv("OPERATION_API_BASE", "https://ops.example.test")
    calls = _watch(
        monkeypatch, "get",
        lambda url, kw: FakeResp(json.dumps({"id": "o", "done": True})),
    )
    assert detail.get_operation("o")["done"] is True
    assert calls[0][0] == "https://ops.example.test/operations/o"


# --- gen search (FOLDER_ID required) ---------------------------------------------
def test_call_gen_search_requires_folder_id(monkeypatch, api_key):
    monkeypatch.delenv("FOLDER_ID", raising=False)
    monkeypatch.delenv("YANDEX_SEARCH_FOLDER_ID", raising=False)
    with pytest.raises(ValueError):
        detail.call_gen_search({"query": "вопрос"})


def test_call_gen_search_body(monkeypatch, api_key):
    monkeypatch.setenv("FOLDER_ID", "folder-1")
    calls = _watch(
        monkeypatch, "post",
        lambda url, kw: FakeResp(json.dumps({"message": {"content": "ответ"}}), kw),
    )
    out = detail.call_gen_search({"query": "вопрос"})
    assert out["message"]["content"] == "ответ"
    body = calls[0][1]["json"]
    assert body["folderId"] == "folder-1"
    assert body["searchType"] == "SEARCH_TYPE_RU"
    assert body["messages"] == [{"role": "ROLE_USER", "content": "вопрос"}]


def test_call_gen_search_partial(monkeypatch, api_key):
    monkeypatch.setenv("FOLDER_ID", "folder-1")
    lines = json.dumps({"a": 1}) + "\n" + json.dumps({"b": 2}) + "\n"
    calls = _watch(monkeypatch, "post", lambda url, kw: FakeResp(lines, kw))
    out = detail.call_gen_search({"query": "x", "get_partial_results": True})
    assert out == {"partial": [{"a": 1}, {"b": 2}]}
    assert calls[0][1]["json"]["getPartialResults"] is True


# --- image search ----------------------------------------------------------------
def test_call_image_search_parses_images(monkeypatch, api_key):
    monkeypatch.setenv("FOLDER_ID", "folder-1")
    xml = """<response>
<doc id="1">
<url>https://img/1.png</url>
<title>Кот</title>
<headline>не нужен</headline>
<width>100</width>
</doc>
<doc id="2">
<url>https://img/2.jpg</url>
<passage>подпись как заголовок</passage>
</doc>
<doc id="3">
<headline>без url</headline>
</doc>
</response>"""
    calls = _watch(monkeypatch, "post", lambda url, kw: FakeResp(_b64_xml(xml), kw))
    out = detail.call_image_search({"query": "кот"})
    assert out["count"] == 2
    assert out["images"][0]["url"] == "https://img/1.png"
    assert "headline" not in out["images"][0]  # dropped for image search
    assert out["images"][1]["title"] == "подпись как заголовок"  # passage fallback
    assert calls[0][0].endswith("/image/search")


def test_call_search_by_image_requires_input(monkeypatch, api_key):
    with pytest.raises(ValueError):
        detail.call_search_by_image({})


def test_call_search_by_image_body(monkeypatch, api_key):
    monkeypatch.setenv("FOLDER_ID", "folder-1")
    calls = _watch(
        monkeypatch, "post",
        lambda url, kw: FakeResp(json.dumps({"images": []}), kw),
    )
    out = detail.call_search_by_image(
        {"url": "https://img/x.png", "site": "example.com", "page": 2,
         "family_mode": "FAMILY_MODE_MODERATE"}
    )
    assert out == {"images": []}
    body = calls[0][1]["json"]
    assert body["url"] == "https://img/x.png"
    assert body["folderId"] == "folder-1"
    assert body["site"] == "example.com"
    assert body["page"] == 2
    assert body["familyMode"] == "FAMILY_MODE_MODERATE"