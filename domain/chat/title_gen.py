"""Topic-aware session title generation (S41).

Generates concise 2–5 word, title-case session titles from the user
query and/or resolved concept, without requiring an LLM round-trip.
"""

from __future__ import annotations

import re

# Words to strip from the beginning of a query for title derivation
_STRIP_PREFIXES = re.compile(
    r"^(can you |could you |please |help me |I want to |tell me about |explain |"
    r"what is |what are |what's |how do |how does |how to |why is |why does |"
    r"describe |define |show me )",
    re.IGNORECASE,
)

_MAX_TITLE_WORDS = 5
_MIN_TITLE_WORDS = 2


def generate_session_title(
    *,
    user_query: str,
    concept_name: str | None = None,
) -> str:
    """Derive a short, topic-aware title for a chat session.

    Strategy:
    1. If a concept was resolved, prefer "{concept_name} Discussion"
       (or just the concept name if it's already ≥2 words).
    2. Otherwise, extract key words from the user query.
    3. Title-case the result, clamp to 2–5 words.
    """
    if concept_name and concept_name.strip():
        name = concept_name.strip()
        words = name.split()
        if len(words) >= _MIN_TITLE_WORDS:
            return _title_case_clamp(words)
        return _title_case_clamp(words + ["Discussion"])

    # Derive from user query
    cleaned = _STRIP_PREFIXES.sub("", user_query.strip())
    cleaned = re.sub(r"[?!.,;:]+$", "", cleaned).strip()
    if not cleaned:
        cleaned = user_query.strip()

    words = cleaned.split()
    if len(words) < _MIN_TITLE_WORDS:
        words.append("Chat")

    return _title_case_clamp(words)


def _title_case_clamp(words: list[str]) -> str:
    """Title-case and clamp to MAX_TITLE_WORDS words."""
    clamped = words[:_MAX_TITLE_WORDS]
    return " ".join(w.capitalize() for w in clamped)
