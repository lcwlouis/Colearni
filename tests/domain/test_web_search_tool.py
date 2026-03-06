"""Tests for WebSearchTool and evidence formatting (L8.1 + L8.4)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.schemas.assistant import EvidenceItem, EvidenceSourceType
from domain.tools.web_search import WebSearchParams, WebSearchTool, format_as_evidence


# ── WebSearchTool tests ──────────────────────────────────────────

def test_web_search_tool_properties() -> None:
    tool = WebSearchTool(api_key="test-key")
    assert tool.name == "web_search"
    assert "web" in tool.description.lower()
    assert tool.parameters_model is WebSearchParams


def test_web_search_tool_rejects_empty_key() -> None:
    with pytest.raises(ValueError, match="web_search_api_key"):
        WebSearchTool(api_key="  ")


@pytest.mark.anyio
async def test_web_search_execute_calls_tavily() -> None:
    tool = WebSearchTool(api_key="test-key", max_results=3)

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {"title": "Result 1", "url": "https://example.com/1", "content": "Content 1"},
            {"title": "Result 2", "url": "https://example.com/2", "content": "Content 2"},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("domain.tools.web_search.httpx.AsyncClient", return_value=mock_client):
        result = await tool.execute(query="test query")

    data = json.loads(result)
    assert data["count"] == 2
    assert len(data["results"]) == 2
    assert data["results"][0]["title"] == "Result 1"


@pytest.mark.anyio
async def test_web_search_execute_handles_http_error() -> None:
    """HTTP errors should return empty results, not raise."""
    import httpx as _httpx

    tool = WebSearchTool(api_key="test-key")

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=_httpx.HTTPError("connection failed"))

    with patch("domain.tools.web_search.httpx.AsyncClient", return_value=mock_client):
        result = await tool.execute(query="test query")

    data = json.loads(result)
    assert data["count"] == 0
    assert data["results"] == []


@pytest.mark.anyio
async def test_web_search_respects_max_results() -> None:
    tool = WebSearchTool(api_key="test-key", max_results=2)

    mock_response = MagicMock()
    mock_response.json.return_value = {"results": []}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("domain.tools.web_search.httpx.AsyncClient", return_value=mock_client):
        await tool.execute(query="test", max_results=10)

    call_args = mock_client.post.call_args
    payload = call_args.kwargs.get("json") or call_args[1].get("json")
    assert payload["max_results"] == 2  # capped by tool's default


# ── format_as_evidence tests ─────────────────────────────────────

def test_format_as_evidence_basic() -> None:
    raw = json.dumps({
        "results": [
            {"title": "Page 1", "url": "https://example.com/1", "content": "Some content"},
            {"title": "Page 2", "url": "https://example.com/2", "content": "More content"},
        ],
        "count": 2,
    })
    items = format_as_evidence(raw)
    assert len(items) == 2
    assert all(isinstance(i, EvidenceItem) for i in items)
    assert items[0].source_type == EvidenceSourceType.WEB
    assert items[0].evidence_id == "web-0"
    assert items[0].content == "Some content"
    assert items[0].source_uri == "https://example.com/1"
    assert items[0].document_title == "Page 1"


def test_format_as_evidence_skips_empty_content() -> None:
    raw = json.dumps({
        "results": [
            {"title": "Empty", "url": "https://example.com", "content": ""},
            {"title": "OK", "url": "https://example.com/2", "content": "Has content"},
        ],
        "count": 2,
    })
    items = format_as_evidence(raw)
    assert len(items) == 1
    assert items[0].content == "Has content"


def test_format_as_evidence_handles_invalid_json() -> None:
    assert format_as_evidence("not json") == []
    assert format_as_evidence("") == []


def test_format_as_evidence_handles_empty_results() -> None:
    raw = json.dumps({"results": [], "count": 0})
    assert format_as_evidence(raw) == []


# ── EvidenceSourceType.WEB validation tests ──────────────────────

def test_web_evidence_accepts_source_uri() -> None:
    item = EvidenceItem(
        evidence_id="web-0",
        source_type=EvidenceSourceType.WEB,
        content="test content",
        source_uri="https://example.com",
    )
    assert item.source_type == EvidenceSourceType.WEB


def test_web_evidence_rejects_workspace_fields() -> None:
    with pytest.raises(ValueError, match="web evidence must not include"):
        EvidenceItem(
            evidence_id="web-0",
            source_type=EvidenceSourceType.WEB,
            content="test content",
            document_id=1,
            chunk_id=1,
            chunk_index=0,
        )
