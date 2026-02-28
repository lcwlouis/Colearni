"""Query analyzer – classifies user messages for routing decisions.

P3: Provides a structured query analysis result with intent, mode hints,
keyword extraction, and level-up readiness signals.  This component does
NOT answer the user's question; it only classifies.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Literal

from core.prompting import PromptRegistry

log = logging.getLogger("domain.chat.query_analyzer")

_registry = PromptRegistry()

Intent = Literal["learn", "practice", "level_up", "explore", "social", "clarify"]
RequestedMode = Literal["socratic", "direct", "unknown"]

_PROMPT_ID = "routing_query_analyzer_v1"


@dataclass(frozen=True)
class QueryAnalysis:
    """Structured result of query analysis."""

    intent: Intent = "clarify"
    requested_mode: RequestedMode = "unknown"
    needs_retrieval: bool = True
    should_offer_level_up: bool = False
    high_level_keywords: list[str] = field(default_factory=list)
    low_level_keywords: list[str] = field(default_factory=list)
    concept_hints: list[str] = field(default_factory=list)


# Conservative fallback for vague or unparseable queries
_FALLBACK = QueryAnalysis(intent="clarify", needs_retrieval=False)


def build_query_analysis_prompt(*, query: str, history_summary: str = "") -> tuple[str, object]:
    """Render the query analysis prompt from the file-based asset.

    Returns (rendered_text, PromptMeta | None).
    """
    try:
        return _registry.render_with_meta(_PROMPT_ID, {
            "query": query,
            "history_summary": history_summary or "(none)",
        })
    except Exception:
        log.debug("asset render_with_meta failed for %s, using inline fallback", _PROMPT_ID)
        return _registry.render(_PROMPT_ID, {
            "query": query,
            "history_summary": history_summary or "(none)",
        }), None


def parse_query_analysis(raw_json: str) -> QueryAnalysis:
    """Parse LLM JSON output into a :class:`QueryAnalysis`.

    Returns the conservative fallback on any parse or validation error.
    """
    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        log.warning("query analysis JSON parse failed, using fallback")
        return _FALLBACK

    if not isinstance(data, dict):
        return _FALLBACK

    intent = data.get("intent", "clarify")
    if intent not in {"learn", "practice", "level_up", "explore", "social", "clarify"}:
        intent = "clarify"

    requested_mode = data.get("requested_mode", "unknown")
    if requested_mode not in {"socratic", "direct", "unknown"}:
        requested_mode = "unknown"

    return QueryAnalysis(
        intent=intent,
        requested_mode=requested_mode,
        needs_retrieval=bool(data.get("needs_retrieval", True)),
        should_offer_level_up=bool(data.get("should_offer_level_up", False)),
        high_level_keywords=_str_list(data.get("high_level_keywords")),
        low_level_keywords=_str_list(data.get("low_level_keywords")),
        concept_hints=_str_list(data.get("concept_hints")),
    )


def _str_list(val: object) -> list[str]:
    """Coerce a value to a list of strings, dropping non-string items."""
    if not isinstance(val, list):
        return []
    return [str(v) for v in val if isinstance(v, str)]


__all__ = [
    "QueryAnalysis",
    "build_query_analysis_prompt",
    "parse_query_analysis",
]
