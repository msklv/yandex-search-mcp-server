"""
Yandex Search API MCP Server (web search)

Provides Yandex Search API v2 web search via MCP. The AI/generative (yazeka)
endpoint is intentionally NOT exposed — only `web_search`.

Russian is the default search type (SEARCH_TYPE_RU, LOCALIZATION_RU, region 225 = Россия).

Modified from yandex/yandex-search-mcp-server (c) 2025 YANDEX LLC, Apache-2.0.
Changes: removed the AI/yazeka endpoint (search-only). Not an official Yandex product.
"""
import json
import re
from typing import Any, Dict

from mcp.server.fastmcp import FastMCP
from detail import validate_input_data, call_web_search

# Create an MCP server
mcp = FastMCP(name="Yandex Search Api v2, web")


def extract_documents_from_xml(xml_content):
    """Извлекает отдельные документы из XML контента"""
    doc_strings = []
    lines = xml_content.split('\n')
    current_doc = []
    in_doc = False

    for line in lines:
        if '<doc ' in line and 'id=' in line:
            in_doc = True
            current_doc = [line]
        elif in_doc and '</doc>' in line:
            current_doc.append(line)
            doc_strings.append('\n'.join(current_doc))
            in_doc = False
        elif in_doc:
            current_doc.append(line)

    return doc_strings


def clean_text(text):
    """Очищает текст от hlword тегов"""
    if not text:
        return ""
    cleaned = re.sub(r'<hlword>|</hlword>', '', text)
    return cleaned.strip()


def extract_document_elements(doc_string):
    """Извлекает элементы из строки документа"""
    url_match = re.search(r'<url>(.*?)</url>', doc_string)
    headline_match = re.search(r'<headline>(.*?)</headline>', doc_string)
    title_match = re.search(r'<title>(.*?)</title>', doc_string)
    passage_matches = re.findall(r'<passage>(.*?)</passage>', doc_string)
    extended_text_match = re.search(r'<extended-text>(.*?)</extended-text>', doc_string)

    return {
        'url': url_match.group(1) if url_match else None,
        'headline': headline_match.group(1) if headline_match else None,
        'title': title_match.group(1) if title_match else None,
        'passages': passage_matches,
        'extended_text': extended_text_match.group(1) if extended_text_match else None
    }


def get_best_content(elements):
    """Выбирает лучший контент из доступных элементов"""
    if elements['headline']:
        return clean_text(elements['headline']), "headline"
    elif elements['title']:
        return clean_text(elements['title']), "title"
    elif elements['passages']:
        cleaned_passages = [clean_text(p) for p in elements['passages'] if p]
        return " ".join(cleaned_passages), "passages"
    elif elements['extended_text']:
        return clean_text(elements['extended_text']), "extended-text"
    else:
        return None, None


def process_single_document(doc_string):
    """Обрабатывает один документ и возвращает результат"""
    elements = extract_document_elements(doc_string)

    if not elements['url']:
        return None

    content, source = get_best_content(elements)

    if content:
        return {
            'data': content,
            'source': elements['url']
        }

    return None


@mcp.tool()
def web_search(body: dict) -> str:
    """
    Search the web via Yandex Search API. Russian by default.

    Args:
        body (dict): required. input containing:
            - query: required. Search query string (Russian supported natively).
            - search_region: optional. Search type code, default 'ru'.
                  'ru'  — Russian (default),
                  'tr'  — Turkish,
                  'com' — International,
                  'kk'  — Kazakh, 'be' — Belarusian, 'uz' — Uzbek.
            - region: optional. Numeric Yandex region id to bias ranking, only for 'ru'/'tr'.
                  Defaults to 225 (Россия) for 'ru'.
                  Examples: 213 = Москва, 2 = Санкт-Петербург.

        minimal example:
            "body": { "query": "кофемашина", "search_region": "ru", "region": 213 }

    Returns:
        dict: array of data and source, as JSON (Chinese-style ensure_ascii=False).
    """
    data = body or {}
    if error_message := validate_input_data(data, {"query"}):
        return error_message

    decoded_data = call_web_search(data)
    doc_strings = extract_documents_from_xml(decoded_data)
    response = {'responses': []}

    for doc_string in doc_strings:
        doc_result = process_single_document(doc_string)
        if doc_result:
            response["responses"].append(doc_result)

    return json.dumps(response, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    try:
        mcp.run(transport="stdio")
    except Exception:
        raise