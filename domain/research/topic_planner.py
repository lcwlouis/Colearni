"""Topic/subtopic planner for research goals (AR5.2).

Accepts a high-level research goal and produces a list of
TopicProposal objects.  Uses an LLM when available; falls back to
a single-topic proposal from the raw goal.

All proposals are pending — the user must approve/narrow before
query planning begins.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from domain.research.planner import SourceClass, TopicProposal

if TYPE_CHECKING:
    from core.contracts import GraphLLMClient

logger = logging.getLogger(__name__)

_MAX_SUBTOPICS = 5
_MAX_PROPOSALS = 5

_TOPIC_PLANNER_PROMPT = """\
You are a research planner for a learning copilot.

Given the user's research goal, propose up to {max_proposals} study topics.
For each topic, suggest up to {max_subtopics} subtopics and recommend
source classes from: paper, article, docs, tutorial, expert_post, update, other.

Respond ONLY with a JSON array. Each element must have:
- "topic": string (concise topic name)
- "subtopics": string[] (specific subtopics or angles)
- "source_classes": string[] (recommended source types)
- "rationale": string (why this topic matters for the goal)
- "priority": "high" | "medium" | "low"

Research goal: {goal}
"""


def plan_topics(
    *,
    goal: str,
    llm_client: "GraphLLMClient | None" = None,
    max_proposals: int = _MAX_PROPOSALS,
) -> list[TopicProposal]:
    """Generate topic proposals from a research goal.

    Returns a list of TopicProposal objects, capped at max_proposals.
    Falls back to a single proposal from the raw goal if LLM is unavailable.
    """
    if not goal.strip():
        return []

    if llm_client is None:
        return [_fallback_proposal(goal)]

    try:
        return _llm_plan_topics(goal=goal, llm_client=llm_client, max_proposals=max_proposals)
    except Exception:
        logger.warning("LLM topic planning failed; using fallback", exc_info=True)
        return [_fallback_proposal(goal)]


def _llm_plan_topics(
    *,
    goal: str,
    llm_client: "GraphLLMClient",
    max_proposals: int,
) -> list[TopicProposal]:
    """Use LLM to generate structured topic proposals."""
    prompt = _TOPIC_PLANNER_PROMPT.format(
        goal=goal,
        max_proposals=max_proposals,
        max_subtopics=_MAX_SUBTOPICS,
    )
    raw = llm_client.generate_tutor_text(prompt=prompt, prompt_meta=None)
    return _parse_proposals(raw, max_proposals=max_proposals)


def _parse_proposals(raw: str, *, max_proposals: int) -> list[TopicProposal]:
    """Parse LLM JSON output into TopicProposal objects."""
    # Strip markdown code fences if present
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

    proposals: list[TopicProposal] = []
    for item in data[:max_proposals]:
        if not isinstance(item, dict) or "topic" not in item:
            continue

        source_classes: list[SourceClass] = []
        for sc in item.get("source_classes", []):
            if sc in ("paper", "article", "docs", "tutorial", "expert_post", "update", "other"):
                source_classes.append(sc)

        priority = item.get("priority", "medium")
        if priority not in ("high", "medium", "low"):
            priority = "medium"

        proposals.append(TopicProposal(
            topic=str(item["topic"]),
            subtopics=[str(s) for s in item.get("subtopics", [])[:_MAX_SUBTOPICS]],
            source_classes=source_classes,
            rationale=str(item.get("rationale", "")),
            priority=priority,
        ))

    if not proposals:
        raise ValueError("No valid proposals parsed")

    return proposals


def _fallback_proposal(goal: str) -> TopicProposal:
    """Create a single proposal from the raw goal text."""
    return TopicProposal(
        topic=goal.strip()[:200],
        rationale="Direct from user research goal",
        priority="medium",
        source_classes=["article", "docs"],
    )
