"""Backend answer-parts splitter (U6).

Replaces the frontend regex-based hint extraction with a deterministic
backend-controlled contract.  The ``split_answer_parts`` function is the
single point of truth for decomposing an assistant answer into structured
parts (body + optional hint).

The tutor prompt (socratic_v1) explicitly forbids rigid ``Hint:`` headers,
so the splitter uses a broader set of heuristic patterns to detect
thinking-out-loud hint content.  If no hint is detected the full text is
returned as the body.
"""

from __future__ import annotations

import re

from core.schemas.assistant import AnswerParts

# Patterns that indicate the start of hint-like content.
# Ordered from most explicit to most implicit.  The first match wins.
_HINT_PATTERNS: list[re.Pattern[str]] = [
    # Explicit bold/emoji hint markers (legacy model outputs)
    re.compile(r"(?:^|\n)\s*(?:\*{1,2})?💡\s*(?:Hint)?(?:\*{1,2})?\s*:?\s*", re.IGNORECASE),
    # Plain or bold "Hint:" header (still emitted by some model variants)
    re.compile(r"(?:^|\n)\s*\*{0,2}(?:Hint|HINT)\*{0,2}\s*:\s*\*{0,2}\s*", re.IGNORECASE),
    # Thinking-out-loud opener prescribed by the socratic prompt
    re.compile(r"(?:^|\n)\s*(?:One way to think about (?:it|this) is)", re.IGNORECASE),
]


def split_answer_parts(text: str) -> AnswerParts:
    """Split assistant text into structured body + optional hint.

    Returns an ``AnswerParts`` with the main body and, if detected, a
    separated hint string.  The hint is stripped of leading markers.
    """
    if not text or not text.strip():
        return AnswerParts(body=text or "")

    for pattern in _HINT_PATTERNS:
        match = pattern.search(text)
        if match:
            body = text[: match.start()].rstrip()
            hint = text[match.end() :].strip()
            if body and hint:
                return AnswerParts(body=body, hint=hint)

    return AnswerParts(body=text.strip())
