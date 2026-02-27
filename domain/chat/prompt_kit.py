"""Prompt kit – versioned prompt templates, persona, and social-intent classifier.

Slice 13: This module provides:
  1. Persona definitions (OpenClaw default + pluggable).
  2. A lightweight social-intent classifier that detects greetings / chitchat
     and routes them to a "social" response path (no retrieval needed).
  3. Versioned prompt builder that composes the final tutor system prompt
     from persona + style + assessment history + evidence blocks.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Literal

from core.schemas import EvidenceItem

# ── Persona Definitions ──────────────────────────────────────────────

PERSONA_OPENCLAW = {
    "name": "OpenClaw",
    "tone": "warm, curious, and encouraging",
    "greeting": "Hey there! I'm OpenClaw, your study buddy. What shall we explore today?",
    "system_prefix": (
        "You are OpenClaw, an encouraging and curious AI tutor. "
        "You love asking guiding questions and celebrating progress. "
        "Keep responses concise, warm, and grounded in the user's study material."
    ),
}

PERSONA_REGISTRY: dict[str, dict[str, str]] = {
    "openclaw": PERSONA_OPENCLAW,
}


def get_persona(name: str) -> dict[str, str]:
    """Resolve a persona by name, defaulting to OpenClaw."""
    return PERSONA_REGISTRY.get(name.lower(), PERSONA_OPENCLAW)


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
        name = persona.get("name", "OpenClaw")
        return f"I'm {name}, your AI study tutor! What shall we work on?"
    return "😊 Let me know when you're ready to study!"


# ── Versioned Prompt Builder ─────────────────────────────────────────

PROMPT_VERSION = "v1"


def build_system_prompt(
    *,
    persona: dict[str, str],
    style: Literal["socratic", "direct"],
    assessment_context: str = "",
    history_summary: str = "",
    document_summaries: str = "",
) -> str:
    """Compose the full system prompt for the tutor LLM call.

    Components (in order):
      1. Persona system prefix
      2. Teaching style rules
      3. Document summaries (if available)
      4. Assessment history summary (if available)
      5. Conversation history summary (if available)
    """
    lines: list[str] = [
        persona.get("system_prefix", PERSONA_OPENCLAW["system_prefix"]),
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

    if assessment_context:
        lines.extend([
            "RECENT ASSESSMENT CONTEXT:",
            assessment_context,
            "",
        ])

    if history_summary:
        lines.extend([
            "CONVERSATION HISTORY:",
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
    assessment_context: str = "",
    history_summary: str = "",
    document_summaries: str = "",
) -> str:
    """Build the complete prompt: system + evidence + user question."""
    system = build_system_prompt(
        persona=persona,
        style=style,
        assessment_context=assessment_context,
        history_summary=history_summary,
        document_summaries=document_summaries,
    )
    evidence_block = build_evidence_block(evidence)
    return f"{system}\n{evidence_block}\n\nUSER_QUESTION: {query}"


__all__ = [
    "PROMPT_VERSION",
    "build_evidence_block",
    "build_full_tutor_prompt",
    "build_social_response",
    "build_system_prompt",
    "classify_social_intent",
    "get_persona",
]
