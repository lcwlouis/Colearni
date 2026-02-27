"""Research runner – fetch, parse, and produce candidates from workspace sources.

This is the async job backend (see apps/jobs/research_runner.py).
Approval-gated: discovered candidates stay "pending" until a user approves → ingests.
"""

from __future__ import annotations

import hashlib
import html
import logging
import re
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.ingestion import IngestionRequest, ingest_text_document

logger = logging.getLogger(__name__)

MAX_CANDIDATES_PER_SOURCE = 25
FETCH_TIMEOUT_SECONDS = 15
MAX_CONTENT_LENGTH = 500_000  # ~500KB text limit per page


def _strip_html(raw_html: str) -> str:
    """Extract readable text from raw HTML."""
    # Remove script/style blocks
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    # Decode HTML entities
    cleaned = html.unescape(cleaned)
    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _extract_title(raw_html: str) -> str | None:
    """Extract <title> from HTML."""
    match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.DOTALL | re.IGNORECASE)
    if match:
        return html.unescape(match.group(1).strip())[:200]
    return None


def run_research(
    session: Session,
    *,
    workspace_id: int,
    run_id: int,
    max_candidates: int = MAX_CANDIDATES_PER_SOURCE,
) -> dict[str, Any]:
    """Execute a research run: fetch sources, discover candidates."""
    session.execute(
        text(
            "UPDATE workspace_research_runs SET status = 'running' "
            "WHERE id = :run_id AND workspace_id = :workspace_id"
        ),
        {"run_id": run_id, "workspace_id": workspace_id},
    )
    session.commit()

    sources = (
        session.execute(
            text(
                "SELECT id, url FROM workspace_research_sources "
                "WHERE workspace_id = :workspace_id AND active = TRUE "
                "ORDER BY id ASC"
            ),
            {"workspace_id": workspace_id},
        )
        .mappings()
        .all()
    )

    # Load existing content fingerprints to avoid duplicates
    existing_fps = set()
    rows = session.execute(
        text(
            "SELECT content_hash FROM workspace_research_candidates "
            "WHERE workspace_id = :workspace_id"
        ),
        {"workspace_id": workspace_id},
    ).all()
    existing_fps = {str(r[0]) for r in rows if r[0]}

    total_candidates = 0
    client = httpx.Client(timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=True)
    try:
        for source in sources:
            url = str(source["url"])
            source_id = int(source["id"])
            try:
                resp = client.get(url)
                resp.raise_for_status()
            except (httpx.HTTPError, httpx.TimeoutException) as exc:
                logger.warning("research_runner: failed to fetch %s: %s", url, exc)
                continue

            # Extract text content
            content_type = resp.headers.get("content-type", "")
            if "html" in content_type:
                raw_text = _strip_html(resp.text[:MAX_CONTENT_LENGTH])
                title = _extract_title(resp.text[:10000]) or url
            elif "text" in content_type:
                raw_text = resp.text[:MAX_CONTENT_LENGTH]
                title = url
            else:
                logger.info("research_runner: skipping %s (content-type: %s)", url, content_type)
                continue

            if len(raw_text.strip()) < 50:
                logger.info("research_runner: skipping %s (too short after extraction)", url)
                continue

            # Fingerprint + dedup
            fp = fingerprint_text(raw_text)
            if fp in existing_fps:
                logger.info("research_runner: skipping %s (duplicate content)", url)
                continue
            existing_fps.add(fp)

            # Break into candidate snippets (take first MAX_CONTENT_LENGTH chars)
            snippet = raw_text[:2000]

            session.execute(
                text(
                    """
                    INSERT INTO workspace_research_candidates
                        (workspace_id, source_id, source_url, title, snippet,
                         content_hash, status, created_at)
                    VALUES
                        (:workspace_id, :source_id, :source_url, :title, :snippet,
                         :content_hash, 'pending', now())
                    """
                ),
                {
                    "workspace_id": workspace_id,
                    "source_id": source_id,
                    "source_url": url,
                    "title": title[:500],
                    "snippet": snippet,
                    "content_hash": fp,
                },
            )
            total_candidates += 1

            if total_candidates >= max_candidates:
                break
    finally:
        client.close()

    session.execute(
        text(
            "UPDATE workspace_research_runs "
            "SET status = 'completed', candidates_found = :count, finished_at = now() "
            "WHERE id = :run_id"
        ),
        {"run_id": run_id, "count": total_candidates},
    )
    session.commit()

    return {
        "run_id": run_id,
        "workspace_id": workspace_id,
        "status": "completed",
        "candidates_found": total_candidates,
    }


def ingest_approved_candidates(
    session: Session,
    *,
    workspace_id: int,
    uploaded_by_user_id: int = 1,
) -> int:
    """Ingest all approved candidates into the document pipeline.

    Returns the count of candidates that were moved to 'ingested' status.
    """
    rows = (
        session.execute(
            text(
                """
                SELECT id, source_url, title, snippet
                FROM workspace_research_candidates
                WHERE workspace_id = :workspace_id AND status = 'approved'
                ORDER BY id ASC
                LIMIT 100
                """
            ),
            {"workspace_id": workspace_id},
        )
        .mappings()
        .all()
    )

    ingested = 0
    for row in rows:
        snippet = str(row["snippet"] or "")
        title = str(row["title"] or "")
        source_url = str(row["source_url"] or "")
        candidate_id = int(row["id"])

        if not snippet.strip():
            logger.info("research_runner: skipping empty candidate %s", candidate_id)
            continue

        try:
            ingest_text_document(
                session,
                request=IngestionRequest(
                    workspace_id=workspace_id,
                    uploaded_by_user_id=uploaded_by_user_id,
                    raw_bytes=snippet.encode("utf-8"),
                    content_type="text/plain",
                    filename=None,
                    title=title or f"Research: {source_url}",
                    source_uri=source_url,
                ),
            )
        except Exception as exc:
            logger.warning("research_runner: failed to ingest candidate %s: %s", candidate_id, exc)
            session.execute(
                text(
                    "UPDATE workspace_research_candidates "
                    "SET status = 'failed' WHERE id = :id"
                ),
                {"id": candidate_id},
            )
            continue

        session.execute(
            text(
                "UPDATE workspace_research_candidates "
                "SET status = 'ingested' WHERE id = :id"
            ),
            {"id": candidate_id},
        )
        ingested += 1

    if ingested:
        session.commit()
    return ingested


def fingerprint_text(text_value: str) -> str:
    """Produce a stable fingerprint from content for dedup."""
    normalized = " ".join(text_value.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


__all__ = [
    "fingerprint_text",
    "ingest_approved_candidates",
    "run_research",
]
