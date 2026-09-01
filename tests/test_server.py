"""Tests for the MCP server — tool registration + each tool's JSON contract.

Requires mcp (pinned <2, i.e. ``mcp[cli]==1.29.1`` where ``FastMCP`` exists).
Network is mocked so no Yandex calls happen.
"""
import json

import pytest

import server

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


def test_all_tools_registered():
    names = set(server.mcp._tool_manager._tools)
    assert {
        "web_search", "web_search_async", "get_operation",
        "gen_search", "image_search", "image_search_by_image",
    } <= names


def test_web_search_returns_parsed_responses(monkeypatch):
    monkeypatch.setattr(server, "call_web_search", lambda body: SAMPLE_XML)
    out = json.loads(server.web_search({"query": "кофе"}))
    # doc 3 has no <url> and is skipped
    assert out["count"] == 2
    assert out["responses"][0] == {
        "data": "Лучшая 2026 кофемашина",
        "source": "https://example.com/1",
    }


def test_web_search_surfaces_errors(monkeypatch):
    monkeypatch.setattr(
        server, "call_web_search",
        lambda body: (_ for _ in ()).throw(ValueError("SEARCH_API_KEY not set")),
    )
    out = json.loads(server.web_search({"query": "x"}))
    assert out["error"].startswith("SEARCH_API_KEY")


def test_web_search_async_contract(monkeypatch):
    monkeypatch.setattr(
        server, "call_web_search_async",
        lambda body: {"id": "op-1", "done": False},
    )
    out = json.loads(server.web_search_async({"query": "x"}))
    assert out == {"id": "op-1", "done": False}


def test_get_operation_contract(monkeypatch):
    monkeypatch.setattr(
        server, "_get_operation",
        lambda op_id: {"id": op_id, "done": True},
    )
    out = json.loads(server.get_operation("op-1"))
    assert out["done"] is True


def test_gen_search_surfaces_folder_id_requirement(monkeypatch):
    monkeypatch.setattr(
        server, "call_gen_search",
        lambda body: (_ for _ in ()).throw(
            ValueError("FOLDER_ID environment variable is required for generative search")
        ),
    )
    out = json.loads(server.gen_search({"query": "вопрос"}))
    assert "FOLDER_ID" in out["error"]


def test_gen_search_ok(monkeypatch):
    monkeypatch.setattr(
        server, "call_gen_search",
        lambda body: {"message": {"content": "ответ"}, "sources": []},
    )
    out = json.loads(server.gen_search({"query": "вопрос"}))
    assert out["message"]["content"] == "ответ"


def test_image_search_contract(monkeypatch):
    monkeypatch.setattr(
        server, "call_image_search",
        lambda body: {"images": [{"url": "https://img/1.png", "title": "Кот"}], "count": 1},
    )
    out = json.loads(server.image_search({"query": "кот"}))
    assert out["count"] == 1
    assert out["images"][0]["url"] == "https://img/1.png"


def test_image_search_by_image_surfaces_error(monkeypatch):
    monkeypatch.setattr(
        server, "call_search_by_image",
        lambda body: (_ for _ in ()).throw(ValueError("search_by_image requires one of: url, data, id")),
    )
    out = json.loads(server.image_search_by_image({}))
    assert "requires one of" in out["error"]