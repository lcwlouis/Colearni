"""Bounded discovery provider for planned queries (AR5.7).

Executes ResearchQuery objects against registered workspace sources,
returning normalized result dicts for the candidate queue.  Provider
budgets are explicit: max queries, max results per query, and total cap.

When no sources are registered or fetching fails, returns an empty list
rather than inserting synthetic placeholders.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from domain.research.planner import ResearchQuery
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT = 10
_MAX_SNIPPET_LEN = 2000
_DEFAULT_MAX_RESULTS_PER_QUERY = 5
_DEFAULT_MAX_TOTAL_RESULTS = 25


def execute_planned_queries(
    session: "Session",
    *,
    workspace_id: int,
    queries: "list[ResearchQuery]",
    max_total_results: int = _DEFAULT_MAX_TOTAL_RESULTS,
) -> list[dict[str, Any]]:
    """Execute planned queries and return normalized candidate dicts.

    Each returned dict has keys: source_url, title, snippet.
    Results stay bounded by per-query and total caps.
    Returns [] when no sources are registered or all fetches fail.
    """
    from sqlalchemy import text as sql_text

    sources = _load_workspace_sources(session, workspace_id=workspace_id)
    if not sources:
        logger.info("discovery_provider: no registered sources for workspace %d", workspace_id)
        return []

    existing_urls = _load_existing_urls(session, workspace_id=workspace_id)
    results: list[dict[str, Any]] = []

    client = httpx.Client(timeout=_FETCH_TIMEOUT, follow_redirects=True)
    try:
        for query in queries:
            if len(results) >= max_total_results:
                break

            per_query_cap = min(
                query.max_results or _DEFAULT_MAX_RESULTS_PER_QUERY,
                max_total_results - len(results),
            )
            query_results = _search_sources(
                client=client,
                sources=sources,
                query=query,
                existing_urls=existing_urls,
                max_results=per_query_cap,
            )
            results.extend(query_results)
    finally:
        client.close()

    logger.info(
        "discovery_provider: %d results from %d queries (workspace %d)",
        len(results), len(queries), workspace_id,
    )
    return results[:max_total_results]


def _load_workspace_sources(
    session: "Session", *, workspace_id: int,
) -> list[dict[str, Any]]:
    """Load active workspace research sources."""
    from sqlalchemy import text as sql_text

    rows = (
        session.execute(
            sql_text(
                "SELECT id, url FROM workspace_research_sources "
                "WHERE workspace_id = :workspace_id AND active = TRUE "
                "ORDER BY id ASC"
            ),
            {"workspace_id": workspace_id},
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


def _load_existing_urls(
    session: "Session", *, workspace_id: int,
) -> set[str]:
    """Load already-known candidate URLs for dedup."""
    from sqlalchemy import text as sql_text

    rows = session.execute(
        sql_text(
            "SELECT source_url FROM workspace_research_candidates "
            "WHERE workspace_id = :workspace_id"
        ),
        {"workspace_id": workspace_id},
    ).all()
    return {str(r[0]) for r in rows if r[0]}


def _search_sources(
    *,
    client: httpx.Client,
    sources: list[dict[str, Any]],
    query: "ResearchQuery",
    existing_urls: set[str],
    max_results: int,
) -> list[dict[str, Any]]:
    """Search registered sources for a single query, returning candidates."""
    results: list[dict[str, Any]] = []

    for source in sources:
        if len(results) >= max_results:
            break

        url = str(source["url"])
        if url in existing_urls:
            continue

        try:
            resp = client.get(url)
            resp.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.debug("discovery_provider: failed to fetch %s: %s", url, exc)
            continue

        content_type = resp.headers.get("content-type", "")
        if "html" in content_type:
            text_content = _strip_html(resp.text[:500_000])
            title = _extract_title(resp.text[:10_000]) or url
        elif "text" in content_type:
            text_content = resp.text[:500_000]
            title = url
        else:
            continue

        if len(text_content.strip()) < 50:
            continue

        # Check relevance: query terms appear in content
        if not _is_relevant(text_content, query.query_text):
            continue

        existing_urls.add(url)
        results.append({
            "source_url": url,
            "title": title[:500],
            "snippet": text_content[:_MAX_SNIPPET_LEN],
        })

    return results


def _is_relevant(content: str, query_text: str) -> bool:
    """Basic relevance check: at least one query term appears in content."""
    terms = query_text.lower().split()
    content_lower = content.lower()
    return any(term in content_lower for term in terms if len(term) > 2)


def _strip_html(raw_html: str) -> str:
    """Extract readable text from HTML."""
    import html as html_mod
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html_mod.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _extract_title(raw_html: str) -> str | None:
    """Extract <title> from HTML."""
    import html as html_mod
    match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.DOTALL | re.IGNORECASE)
    if match:
        return html_mod.unescape(match.group(1).strip())[:200]
    return None


__all__ = ["execute_planned_queries"]
