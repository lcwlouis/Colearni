"""Query analyzer – classifies user messages for routing decisions.

P3: Provides a structured query analysis result with intent, mode hints,
keyword extraction, and level-up readiness signals.  This component does
NOT answer the user's question; it only classifies.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from core.llm_messages import MessageBuilder
from core.llm_schemas import QueryAnalysisResponse
from core.prompting import PromptRegistry

log = logging.getLogger("domain.chat.query_analyzer")

_registry = PromptRegistry()

Intent = Literal["learn", "practice", "level_up", "explore", "social", "clarify"]
RequestedMode = Literal["socratic", "direct", "unknown"]

_PROMPT_ID = "routing_query_analyzer_v1"

_QUERY_ANALYZER_SYSTEM = (
    "You are a query analysis component for Colearni's conductor. "
    "Classify the learner's request so the system can choose the right response path. "
    "Do not answer the learner's question. Return valid JSON only."
)

_QUERY_ANALYSIS_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["learn", "practice", "level_up", "explore", "social", "clarify"],
        },
        "requested_mode": {
            "type": "string",
            "enum": ["socratic", "direct", "unknown"],
        },
        "needs_retrieval": {"type": "boolean"},
        "should_offer_level_up": {"type": "boolean"},
        "high_level_keywords": {"type": "array", "items": {"type": "string"}},
        "low_level_keywords": {"type": "array", "items": {"type": "string"}},
        "concept_hints": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "intent",
        "requested_mode",
        "needs_retrieval",
        "should_offer_level_up",
        "high_level_keywords",
        "low_level_keywords",
        "concept_hints",
    ],
    "additionalProperties": False,
}
_QUERY_ANALYSIS_SCHEMA_NAME = "query_analysis"


@dataclass(frozen=True)
class QueryAnalysis:
    """Structured result of query analysis."""

    intent: Intent = "clarify"
    requested_mode: RequestedMode = "unknown"
    needs_retrieval: bool = True
    should_offer_level_up: bool = False
    needs_web_search: bool = False
    high_level_keywords: list[str] = field(default_factory=list)
    low_level_keywords: list[str] = field(default_factory=list)
    concept_hints: list[str] = field(default_factory=list)


# Conservative fallback — always retrieve to preserve grounded behavior
_FALLBACK = QueryAnalysis(intent="clarify", needs_retrieval=True)


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


def build_query_analysis_messages(*, query: str, history_summary: str = "") -> MessageBuilder:
    """Build multi-message list for query analysis.

    Returns a :class:`MessageBuilder` with a system instruction and a user
    message containing the query and history context.
    """
    prompt_text, _ = build_query_analysis_prompt(
        query=query,
        history_summary=history_summary,
    )
    return (
        MessageBuilder()
        .system(_QUERY_ANALYZER_SYSTEM)
        .user(prompt_text)
    )


def parse_query_analysis(raw_json: str | dict) -> QueryAnalysis:
    """Parse LLM JSON output into a :class:`QueryAnalysis`.

    Returns the conservative fallback on any parse or validation error.
    """
    try:
        if isinstance(raw_json, dict):
            data = raw_json
        else:
            data = json.loads(raw_json)
        validated = QueryAnalysisResponse.model_validate(data)
        intent = validated.intent
        return QueryAnalysis(
            intent=intent,
            requested_mode=validated.requested_mode,
            needs_retrieval=validated.needs_retrieval,
            should_offer_level_up=validated.should_offer_level_up,
            needs_web_search=intent == "explore",
            high_level_keywords=validated.high_level_keywords,
            low_level_keywords=validated.low_level_keywords,
            concept_hints=validated.concept_hints,
        )
    except Exception:
        log.warning("query analysis parse/validation failed, using fallback")
        return _FALLBACK


def run_query_analysis(
    *,
    query: str,
    history_summary: str = "",
    llm_client: Any | None = None,
) -> QueryAnalysis:
    """Run query analysis using the LLM and return a typed result.

    Returns the conservative fallback on LLM unavailability, model errors,
    or parse failures.  This is the primary entrypoint for wiring query
    analysis into the tutor runtime.
    """
    if llm_client is None:
        log.debug("query analysis skipped: no LLM client")
        return _FALLBACK

    messages = build_query_analysis_messages(
        query=query,
        history_summary=history_summary,
    ).build()

    try:
        data = llm_client.complete_messages_json(
            messages,
            schema_name=_QUERY_ANALYSIS_SCHEMA_NAME,
            schema=_QUERY_ANALYSIS_SCHEMA,
        )
    except (RuntimeError, ValueError) as exc:
        log.warning("query analysis LLM call failed: %s", exc)
        return _FALLBACK
    except Exception:
        log.warning("query analysis LLM call failed unexpectedly", exc_info=True)
        return _FALLBACK

    return parse_query_analysis(data)


__all__ = [
    "QueryAnalysis",
    "build_query_analysis_messages",
    "build_query_analysis_prompt",
    "parse_query_analysis",
    "run_query_analysis",
]
