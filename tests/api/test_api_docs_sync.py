from __future__ import annotations

import re
from pathlib import Path

from apps.api.main import app

API_DOC_PATH = Path(__file__).resolve().parents[2] / "docs" / "API.md"
DOC_ENDPOINT_HEADING = re.compile(r"^###\s+([A-Z]+)\s+(\/\S+)\s*$", re.MULTILINE)
EXCLUDED_METHODS = {"head", "options"}


def _doc_routes() -> list[tuple[str, str]]:
    content = API_DOC_PATH.read_text(encoding="utf-8")
    return [
        (path, method.lower())
        for method, path in DOC_ENDPOINT_HEADING.findall(content)
    ]


def _openapi_routes() -> set[tuple[str, str]]:
    spec = app.openapi()
    return {
        (path, method)
        for path, methods in spec["paths"].items()
        for method in methods
        if method not in EXCLUDED_METHODS
    }


def test_api_doc_endpoint_headings_are_unique() -> None:
    doc_routes = _doc_routes()
    assert doc_routes
    assert len(doc_routes) == len(set(doc_routes))


def test_api_doc_endpoint_headings_match_openapi() -> None:
    doc_routes = set(_doc_routes())
    openapi_routes = _openapi_routes()
    assert doc_routes == openapi_routes
