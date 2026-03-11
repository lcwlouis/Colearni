"""Prompt kit – versioned prompt templates, persona, and social-intent classifier.

Slice 13 + P2: This module provides:
  1. Persona definitions (CoLearni default + pluggable).
  2. A lightweight social-intent classifier that detects greetings / chitchat
     and routes them to a "social" response path (no retrieval needed).
  3. Versioned prompt builder that composes the final tutor system prompt
     from file-based prompt assets (P2) with inline fallback.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from core.llm_messages import MessageBuilder
from core.prompting import PromptRegistry
from core.schemas import EvidenceItem, GroundingMode


@dataclass
class PromptMessages:
    """Structured prompt with separate system and user messages."""

    system: str
    user: str

log = logging.getLogger("domain.chat.prompt_kit")

_registry = PromptRegistry()

# ── Persona Definitions ──────────────────────────────────────────────

PERSONA_COLEARNI = {
    "name": "CoLearni",
    "tone": "warm, curious, and encouraging",
    "greeting": "Hey there! I'm CoLearni, your study buddy. What shall we explore today?",
    "system_prefix": (
        "You are CoLearni, an encouraging and curious AI tutor. "
        "You love asking guiding questions and celebrating progress. "
        "Keep responses concise, warm, and grounded in the user's study material."
    ),
}

PERSONA_REGISTRY: dict[str, dict[str, str]] = {
    "colearni": PERSONA_COLEARNI,
}


def get_persona(name: str) -> dict[str, str]:
    """Resolve a persona by name, defaulting to CoLearni."""
    return PERSONA_REGISTRY.get(name.lower(), PERSONA_COLEARNI)


# ── Social-Intent Classifier ─────────────────────────────────────────

_SOCIAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*(hi|hello|hey|howdy|yo|sup|hiya|good\s+(morning|afternoon|evening))\b", re.I),
    re.compile(r"^\s*(thanks?|thank\s+you|thx|ty|cheers)\b", re.I),
    re.compile(r"^\s*(bye|goodbye|see\s+you|later|cya|take\s+care)\b", re.I),
    re.compile(r"^\s*how\s+are\s+you\b", re.I),
    re.compile(r"^\s*what('?s|\s+is)\s+your\s+name\b", re.I),
    re.compile(r"^\s*(lol|haha|hehe|😂|😄|👋)\s*$", re.I),
]


def classify_social_intent(query: str) -> bool:
    """Return True if the query is social/chitchat rather than a study question."""
    normalized = query.strip()
    if len(normalized) < 2:
        return True
    return any(pattern.search(normalized) for pattern in _SOCIAL_PATTERNS)


def build_social_response(query: str, *, persona: dict[str, str]) -> str:
    """Generate a short social/chitchat reply from the persona."""
    lower = query.strip().lower()
    if any(w in lower for w in ("hi", "hello", "hey", "howdy", "yo", "sup", "hiya")):
        return persona.get("greeting", "Hello! What would you like to study?")
    if any(w in lower for w in ("thanks", "thank you", "thx", "ty", "cheers")):
        return "You're welcome! Let me know if you want to keep going. 🎯"
    if any(w in lower for w in ("bye", "goodbye", "see you", "later", "cya")):
        return "See you next time! Keep up the great work. 👋"
    if "how are you" in lower:
        return "I'm doing great, thanks for asking! Ready to help you learn. 📚"
    if "your name" in lower:
        name = persona.get("name", "CoLearni")
        return f"I'm {name}, your AI study tutor! What shall we work on?"
    return "😊 Let me know when you're ready to study!"


# ── Versioned Prompt Builder ─────────────────────────────────────────

PROMPT_VERSION = "v1"

# Map style to prompt asset ID
_TUTOR_ASSET_IDS: dict[str, str] = {
    "socratic": "tutor_socratic_v1",
    "direct": "tutor_direct_v1",
    "socratic_interactive": "tutor_socratic_interactive_v1",
}


def build_system_prompt(
    *,
    persona: dict[str, str],
    style: Literal["socratic", "direct"],
    grounding_mode: GroundingMode = GroundingMode.STRICT,
    assessment_context: str = "",
    history_summary: str = "",
    document_summaries: str = "",
    flashcard_progress: str = "",
) -> str:
    """Compose the full system prompt for the tutor LLM call.

    P2: Now loads from file-based prompt assets with inline fallback.
    """
    asset_id = _TUTOR_ASSET_IDS.get(style, "tutor_socratic_v1")
    strict_grounded_mode = "true" if grounding_mode == GroundingMode.STRICT else "false"
    try:
        return _registry.render(asset_id, {
            "strict_grounded_mode": strict_grounded_mode,
            "mastery_status": "learned" if style == "direct" else "locked",
            "document_summaries": document_summaries or "(none)",
            "graph_context": "(none)",
            "assessment_context": assessment_context or "(none)",
            "flashcard_progress": flashcard_progress or "(none)",
            "history_summary": history_summary or "(none)",
            "evidence_block": "(see below)",
            "query": "(see below)",
        })
    except Exception:
        log.debug("asset load failed for %s, using inline fallback", asset_id)
        return _build_system_prompt_inline(
            persona=persona,
            style=style,
            assessment_context=assessment_context,
            history_summary=history_summary,
            document_summaries=document_summaries,
            flashcard_progress=flashcard_progress,
        )


def _build_system_prompt_inline(
    *,
    persona: dict[str, str],
    style: Literal["socratic", "direct"],
    assessment_context: str = "",
    history_summary: str = "",
    document_summaries: str = "",
    graph_context: str = "",
    flashcard_progress: str = "",
) -> str:
    """Inline fallback for system prompt assembly (pre-P2 behavior)."""
    lines: list[str] = [
        persona.get("system_prefix", PERSONA_COLEARNI["system_prefix"]),
        "",
    ]

    if style == "socratic":
        lines.extend([
            "TEACHING STYLE: Socratic",
            "- Do NOT give the final answer directly.",
            "- Ask one guiding question first, then give a brief hint.",
            "- Encourage the student to reason through the problem.",
            "",
        ])
    else:
        lines.extend([
            "TEACHING STYLE: Direct",
            "- Provide a clear, concise explanation.",
            "- Be grounded in the cited evidence.",
            "- Summarize key points efficiently.",
            "",
        ])

    if document_summaries:
        lines.extend([
            "DOCUMENT SUMMARIES (for context about the user's study material):",
            document_summaries,
            "",
        ])

    if graph_context:
        lines.extend([
            "GRAPH CONTEXT (concept relationships for explanation support):",
            graph_context,
            "",
        ])

    if assessment_context:
        lines.extend([
            "TOPIC ASSESSMENT HISTORY:",
            assessment_context,
            "",
        ])

    if flashcard_progress:
        lines.extend([
            flashcard_progress,
            "",
        ])

    if history_summary:
        lines.extend([
            history_summary,
            "",
        ])

    return "\n".join(lines)


def build_evidence_block(evidence: Sequence[EvidenceItem], *, max_items: int = 5) -> str:
    """Format evidence items into a prompt block."""
    if not evidence:
        return "EVIDENCE:\n- (none available)"

    lines = ["EVIDENCE:"]
    for i, item in enumerate(evidence[:max_items], start=1):
        content = " ".join(item.content.split())[:300]
        lines.append(f"- e{i}: {content}")
    return "\n".join(lines)


def build_full_tutor_prompt(
    *,
    query: str,
    evidence: Sequence[EvidenceItem],
    persona: dict[str, str],
    style: Literal["socratic", "direct"],
    grounding_mode: GroundingMode = GroundingMode.STRICT,
    assessment_context: str = "",
    history_summary: str = "",
    document_summaries: str = "",
    flashcard_progress: str = "",
    learner_profile_summary: str = "",
) -> str:
    """Build the complete prompt: system + evidence + user question.

    P2: Uses file-based prompt assets with inline fallback.
    """
    evidence_block = build_evidence_block(evidence)
    asset_id = _TUTOR_ASSET_IDS.get(style, "tutor_socratic_v1")
    strict_grounded_mode = "true" if grounding_mode == GroundingMode.STRICT else "false"

    try:
        return _registry.render(asset_id, {
            "strict_grounded_mode": strict_grounded_mode,
            "mastery_status": "learned" if style == "direct" else "locked",
            "document_summaries": document_summaries or "(none)",
            "graph_context": "(none)",
            "assessment_context": assessment_context or "(none)",
            "flashcard_progress": flashcard_progress or "(none)",
            "learner_profile_summary": learner_profile_summary or "(none)",
            "history_summary": history_summary or "(none)",
            "evidence_block": evidence_block,
            "query": query,
        })
    except Exception:
        log.debug("asset render failed for %s, using inline fallback", asset_id)
        system = _build_system_prompt_inline(
            persona=persona,
            style=style,
            assessment_context=assessment_context,
            history_summary=history_summary,
            document_summaries=document_summaries,
            flashcard_progress=flashcard_progress,
        )
        return f"{system}\n{evidence_block}\n\nUSER_QUESTION: {query}"


def _build_persona_prefix(
    *,
    persona: dict[str, str],
    style: Literal["socratic", "direct"],
) -> str:
    """Build the stable persona + teaching-style prefix (cacheable).

    Loads the stable (non-variable) sections from the versioned prompt
    template — everything before ``---Inputs---``.  This produces a prefix
    that is identical across turns for the same style, enabling prompt
    caching with providers that support it (e.g. Anthropic).

    Falls back to a compact inline prefix if the asset cannot be loaded.
    """
    asset_id = _TUTOR_ASSET_IDS.get(style, "tutor_socratic_v1")
    try:
        asset = _registry.get(asset_id)
        parts = asset.template.split("---Inputs---", 1)
        if len(parts) == 2:
            stable = parts[0].rstrip()
            if stable:
                return stable
    except Exception:
        log.debug("stable prefix load failed for %s, using inline fallback", asset_id)
    return _build_persona_prefix_inline(persona=persona, style=style)


def _build_persona_prefix_inline(
    *,
    persona: dict[str, str],
    style: Literal["socratic", "direct"],
) -> str:
    """Inline fallback for persona prefix when template loading fails."""
    lines: list[str] = [
        persona.get("system_prefix", PERSONA_COLEARNI["system_prefix"]),
        "",
    ]
    if style == "socratic":
        lines.extend([
            "TEACHING STYLE: Socratic",
            "- Do NOT give the final answer directly.",
            "- Ask one guiding question first, then give a brief hint.",
            "- Encourage the student to reason through the problem.",
        ])
    else:
        lines.extend([
            "TEACHING STYLE: Direct",
            "- Provide a clear, concise explanation.",
            "- Be grounded in the cited evidence.",
            "- Summarize key points efficiently.",
        ])
    return "\n".join(lines)


def build_tutor_messages(
    *,
    query: str,
    evidence: Sequence[EvidenceItem],
    persona: dict[str, str],
    style: Literal["socratic", "direct"],
    grounding_mode: GroundingMode = GroundingMode.STRICT,
    assessment_context: str = "",
    history_summary: str = "",
    document_summaries: str = "",
    graph_context: str = "",
    flashcard_progress: str = "",
    learner_profile_summary: str = "",
    history_turns: list[tuple[str, str]] | None = None,
    compacted_summary: str = "",
) -> tuple[MessageBuilder, object]:
    """Build the tutor prompt as a :class:`MessageBuilder`.

    Returns ``(MessageBuilder, PromptMeta | None)``.  The builder separates
    the stable persona prefix from variable per-turn context blocks so that
    providers can leverage prompt-caching on the prefix.
    """
    # Try to obtain PromptMeta from the registry (for tracing / versioning).
    asset_id = _TUTOR_ASSET_IDS.get(style, "tutor_socratic_v1")
    strict_grounded_mode = "true" if grounding_mode == GroundingMode.STRICT else "false"
    meta = None
    try:
        _, meta = _registry.render_with_meta(asset_id, {
            "strict_grounded_mode": strict_grounded_mode,
            "mastery_status": "learned" if style == "direct" else "locked",
            "document_summaries": document_summaries or "(none)",
            "graph_context": graph_context or "(none)",
            "assessment_context": assessment_context or "(none)",
            "flashcard_progress": flashcard_progress or "(none)",
            "learner_profile_summary": learner_profile_summary or "(none)",
            "history_summary": history_summary or "(none)",
            "evidence_block": "(see user message)",
            "query": "(see user message)",
        })
    except Exception:
        log.debug("asset render_with_meta failed for %s, meta unavailable", asset_id)

    builder = MessageBuilder()

    # Stable prefix (cacheable – doesn't change per turn for a given style)
    builder.system(_build_persona_prefix(persona=persona, style=style))

    # Variable context blocks (skipped when empty)
    if document_summaries:
        builder.context(document_summaries, label="documents")
    if graph_context:
        builder.context(graph_context, label="graph")
    if assessment_context:
        builder.context(assessment_context, label="assessment")
    if flashcard_progress:
        builder.context(flashcard_progress, label="flashcards")
    if learner_profile_summary:
        builder.context(learner_profile_summary, label="learner_profile")

    # History: prefer discrete turns over summary block
    if history_turns is not None:
        if compacted_summary:
            builder.context(compacted_summary, label="compacted_history")
    elif history_summary:
        builder.context(history_summary, label="history")

    # Evidence as its own context block (separate from user query)
    if evidence:
        evidence_block = build_evidence_block(evidence)
        builder.context(evidence_block, label="evidence")

    # Discrete history turns (user/assistant pairs) — after all system blocks
    if history_turns is not None:
        builder.history(history_turns)

    # User message: query only
    builder.user(query)

    return builder, meta


def _flatten_builder(builder: MessageBuilder) -> PromptMessages:
    """Collapse a MessageBuilder into a single PromptMessages (compat helper)."""
    msgs = builder.messages
    system_parts = [m["content"] for m in msgs if m["role"] == "system"]
    user_parts = [m["content"] for m in msgs if m["role"] == "user"]
    return PromptMessages(
        system="\n\n".join(system_parts),
        user="\n\n".join(user_parts),
    )


def build_full_tutor_prompt_with_meta(
    *,
    query: str,
    evidence: Sequence[EvidenceItem],
    persona: dict[str, str],
    style: Literal["socratic", "direct"],
    grounding_mode: GroundingMode = GroundingMode.STRICT,
    assessment_context: str = "",
    history_summary: str = "",
    document_summaries: str = "",
    graph_context: str = "",
    flashcard_progress: str = "",
    learner_profile_summary: str = "",
) -> tuple[PromptMessages, object]:
    """Build the complete prompt and return (PromptMessages, PromptMeta | None).

    Compatibility wrapper around :func:`build_tutor_messages`.  Flattens the
    structured ``MessageBuilder`` back into a single ``PromptMessages`` so
    that existing callers continue to work without changes.
    """
    builder, meta = build_tutor_messages(
        query=query,
        evidence=evidence,
        persona=persona,
        style=style,
        grounding_mode=grounding_mode,
        assessment_context=assessment_context,
        history_summary=history_summary,
        document_summaries=document_summaries,
        graph_context=graph_context,
        flashcard_progress=flashcard_progress,
        learner_profile_summary=learner_profile_summary,
    )
    return _flatten_builder(builder), meta


def build_socratic_interactive_messages(
    *,
    query: str,
    evidence: Sequence[EvidenceItem],
    tutor_state_text: str,
    command_context: str = "",
    history_summary: str = "",
    document_summaries: str = "",
) -> tuple[MessageBuilder, object]:
    """Build Socratic interactive prompt as a :class:`MessageBuilder`.

    Returns ``(MessageBuilder, PromptMeta | None)``.
    """
    meta = None
    try:
        _, meta = _registry.render_with_meta("tutor_socratic_interactive_v1", {
            "tutor_state": tutor_state_text,
            "command_context": command_context or "(no command — regular message)",
            "evidence_block": "(see user message)",
            "history_summary": history_summary or "(none)",
            "query": "(see user message)",
            "document_summaries": document_summaries or "(none)",
        })
    except Exception:
        log.debug("socratic interactive asset failed, meta unavailable")

    builder = MessageBuilder()

    # Stable prefix
    builder.system("You are a Socratic tutor.")

    # Variable context blocks
    builder.context(f"STATE:\n{tutor_state_text}", label="tutor_state")
    if command_context:
        builder.context(f"COMMAND: {command_context}", label="command")
    if document_summaries:
        builder.context(document_summaries, label="documents")
    if history_summary:
        builder.context(history_summary, label="history")

    # User message: evidence + query
    evidence_block = build_evidence_block(evidence)
    builder.user(f"{evidence_block}\n\nUSER: {query}")

    return builder, meta


def build_socratic_interactive_prompt(
    *,
    query: str,
    evidence: Sequence[EvidenceItem],
    tutor_state_text: str,
    command_context: str = "",
    history_summary: str = "",
    document_summaries: str = "",
) -> tuple[PromptMessages, object]:
    """Build prompt for the Socratic interactive protocol.

    Compatibility wrapper around :func:`build_socratic_interactive_messages`.
    Returns ``(PromptMessages, PromptMeta | None)``.
    """
    builder, meta = build_socratic_interactive_messages(
        query=query,
        evidence=evidence,
        tutor_state_text=tutor_state_text,
        command_context=command_context,
        history_summary=history_summary,
        document_summaries=document_summaries,
    )
    return _flatten_builder(builder), meta


__all__ = [
    "PROMPT_VERSION",
    "PromptMessages",
    "build_evidence_block",
    "build_full_tutor_prompt",
    "build_full_tutor_prompt_with_meta",
    "build_socratic_interactive_messages",
    "build_socratic_interactive_prompt",
    "build_social_response",
    "build_system_prompt",
    "build_tutor_messages",
    "classify_social_intent",
    "get_persona",
]
