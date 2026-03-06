"""Query planning and candidate queue integration (AR5.3).

Generates query plans from approved TopicProposals and routes results
into the existing candidate queue.  Does not auto-ingest — all results
enter as pending candidates requiring user approval.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from core.llm_messages import MessageBuilder
from domain.research.planner import (
    ResearchQuery,
    ResearchQueryPlan,
    TopicProposal,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from core.contracts import GraphLLMClient

logger = logging.getLogger(__name__)

_MAX_QUERIES_PER_PLAN = 8
_MAX_CANDIDATES_PER_PLAN = 25

_QUERY_PLANNER_SYSTEM = """\
You are a research query planner for a learning copilot.

Given the approved topic and its subtopics, generate up to {max_queries} search
queries that would find high-quality learning material.

For each query, specify:
- "query_text": string (the search query)
- "source_class": one of "paper", "article", "docs", "tutorial", "expert_post", "update", "other"
- "max_results": integer (1-10)

Respond ONLY with a JSON array of query objects."""

_QUERY_PLANNER_USER = """\
Topic: {topic}
Subtopics: {subtopics}
Source preferences: {source_classes}"""


def build_query_plan(
    *,
    proposal: TopicProposal,
    llm_client: "GraphLLMClient | None" = None,
    max_queries: int = _MAX_QUERIES_PER_PLAN,
) -> ResearchQueryPlan:
    """Generate a ResearchQueryPlan from an approved TopicProposal.

    Falls back to simple keyword queries if LLM is unavailable.
    """
    if llm_client is None:
        return _fallback_query_plan(proposal, max_queries=max_queries)

    try:
        return _llm_query_plan(proposal=proposal, llm_client=llm_client, max_queries=max_queries)
    except Exception:
        logger.warning("LLM query planning failed; using fallback", exc_info=True)
        return _fallback_query_plan(proposal, max_queries=max_queries)


def _llm_query_plan(
    *,
    proposal: TopicProposal,
    llm_client: "GraphLLMClient",
    max_queries: int,
) -> ResearchQueryPlan:
    """Use LLM to generate a structured query plan."""
    system = _QUERY_PLANNER_SYSTEM.format(max_queries=max_queries)
    prompt = _QUERY_PLANNER_USER.format(
        topic=proposal.topic,
        subtopics=", ".join(proposal.subtopics) or "(none)",
        source_classes=", ".join(proposal.source_classes) or "(any)",
    )
    messages = MessageBuilder().system(system).user(prompt).build()
    raw, _ = llm_client.complete_messages(messages)
    queries = _parse_queries(raw, max_queries=max_queries)

    return ResearchQueryPlan(
        topic=proposal.topic,
        queries=queries,
        max_total_candidates=_MAX_CANDIDATES_PER_PLAN,
        rationale=f"Generated from proposal: {proposal.rationale}",
    )


def _parse_queries(raw: str, *, max_queries: int) -> list[ResearchQuery]:
    """Parse LLM JSON output into ResearchQuery objects."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("Expected JSON array")

    queries: list[ResearchQuery] = []
    valid_classes = {"paper", "article", "docs", "tutorial", "expert_post", "update", "other"}

    for item in data[:max_queries]:
        if not isinstance(item, dict) or "query_text" not in item:
            continue

        source_class = item.get("source_class", "other")
        if source_class not in valid_classes:
            source_class = "other"

        max_results = min(int(item.get("max_results", 10)), 10)
        if max_results < 1:
            max_results = 5

        queries.append(ResearchQuery(
            query_text=str(item["query_text"]),
            source_class=source_class,
            max_results=max_results,
        ))

    return queries


def _fallback_query_plan(proposal: TopicProposal, *, max_queries: int) -> ResearchQueryPlan:
    """Build a simple query plan from the topic name and subtopics."""
    queries: list[ResearchQuery] = [
        ResearchQuery(query_text=proposal.topic, source_class="article"),
    ]
    for sub in proposal.subtopics[:max_queries - 1]:
        queries.append(ResearchQuery(
            query_text=f"{proposal.topic} {sub}",
            source_class=proposal.source_classes[0] if proposal.source_classes else "article",
        ))

    return ResearchQueryPlan(
        topic=proposal.topic,
        queries=queries[:max_queries],
        max_total_candidates=_MAX_CANDIDATES_PER_PLAN,
        rationale="Fallback: keyword queries from topic and subtopics",
    )


def enqueue_query_results(
    session: "Session",
    *,
    workspace_id: int,
    run_id: int,
    results: list[dict],
) -> int:
    """Insert query results as pending candidates in the research queue.

    Each result dict must have at least 'source_url'.  Optional: 'title', 'snippet'.
    Returns the number of candidates inserted.

    No content is ingested — all candidates enter as 'pending'.
    """
    from sqlalchemy import text as sql_text

    inserted = 0
    for result in results[:_MAX_CANDIDATES_PER_PLAN]:
        source_url = result.get("source_url", "").strip()
        if not source_url:
            continue

        title = result.get("title", "")[:500] if result.get("title") else None
        snippet = result.get("snippet", "")[:2000] if result.get("snippet") else None

        try:
            session.execute(
                sql_text(
                    "INSERT INTO workspace_research_candidates "
                    "(workspace_id, run_id, source_url, title, snippet, status, created_at) "
                    "VALUES (:workspace_id, :run_id, :source_url, :title, :snippet, 'pending', now())"
                ),
                {
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "source_url": source_url,
                    "title": title,
                    "snippet": snippet,
                },
            )
            inserted += 1
        except Exception:
            logger.debug("Failed to insert candidate for %s", source_url, exc_info=True)

    if inserted > 0:
        session.commit()
        logger.info("Enqueued %d candidates for run %d", inserted, run_id)

    return inserted
