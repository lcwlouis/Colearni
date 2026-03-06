"""Web search tool backed by the Tavily Search API."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

from core.schemas.assistant import EvidenceItem, EvidenceSourceType
from core.tools import Tool

_LOGGER = logging.getLogger(__name__)
_TAVILY_SEARCH_URL = "https://api.tavily.com/search"


class WebSearchParams(BaseModel):
    """Parameters for a web search query."""

    query: str = Field(min_length=1, description="The search query to execute.")
    max_results: int = Field(
        default=5, ge=1, le=20, description="Maximum number of results."
    )


class WebSearchTool:
    """Searches the web via Tavily and returns structured results.

    Implements the ``Tool`` protocol from ``core.tools``.
    """

    def __init__(self, *, api_key: str, max_results: int = 5) -> None:
        if not api_key.strip():
            raise ValueError("web_search_api_key is required")
        self._api_key = api_key.strip()
        self._default_max_results = max_results

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the web for current information on a topic. "
            "Returns titles, URLs, and content snippets from relevant pages."
        )

    @property
    def parameters_model(self) -> type[BaseModel]:
        return WebSearchParams

    async def execute(self, **kwargs: Any) -> str:
        params = WebSearchParams(**kwargs)
        max_results = min(params.max_results, self._default_max_results)
        results = await self._search(params.query, max_results)
        return json.dumps({"results": results, "count": len(results)})

    async def _search(self, query: str, max_results: int) -> list[dict[str, str]]:
        """Call Tavily Search API and return simplified results."""
        payload = {
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False,
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    _TAVILY_SEARCH_URL,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._api_key}",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            _LOGGER.warning("Web search failed: %s", exc)
            return []

        items: list[dict[str, str]] = []
        for result in data.get("results", []):
            items.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", ""),
            })
        return items


def format_as_evidence(raw_results: str) -> list[EvidenceItem]:
    """Convert raw web search JSON results into EvidenceItem list."""
    try:
        data = json.loads(raw_results)
    except (json.JSONDecodeError, TypeError):
        return []

    items: list[EvidenceItem] = []
    for i, result in enumerate(data.get("results", [])):
        content = result.get("content", "").strip()
        if not content:
            continue
        items.append(
            EvidenceItem(
                evidence_id=f"web-{i}",
                source_type=EvidenceSourceType.WEB,
                content=content,
                source_uri=result.get("url"),
                document_title=result.get("title"),
            )
        )
    return items
