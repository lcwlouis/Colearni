"""Lightweight token-counting helper used by graph windowing."""

from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)


def count_text_tokens(text: str, model: str) -> int:
    """Count tokens in *text* for the given model using litellm.

    Falls back to word-based estimation (1 word ≈ 1.3 tokens) if
    litellm is unavailable or the model is unknown.
    """
    try:
        import litellm  # noqa: PLC0415

        return litellm.token_counter(model=model, text=text)
    except Exception:
        estimate = int(len(text.split()) * 1.3)
        _LOGGER.debug(
            "litellm token counting unavailable for %s; falling back to word estimate (%d)",
            model,
            estimate,
        )
        return estimate


def truncate_to_tokens(
    text: str,
    max_tokens: int,
    model: str = "gpt-4o-mini",
    *,
    suffix: str = "…",
) -> str:
    """Truncate *text* to fit within *max_tokens*, cutting at word boundaries.

    Returns *text* unchanged if it already fits.  Otherwise binary-searches
    for the character position that keeps the token count at or below
    *max_tokens* (minus the suffix overhead) and appends *suffix*.
    """
    if not text or max_tokens <= 0:
        return "" if max_tokens <= 0 else text

    total = count_text_tokens(text, model)
    if total <= max_tokens:
        return text

    suffix_tokens = count_text_tokens(suffix, model) if suffix else 0
    target = max_tokens - suffix_tokens
    if target <= 0:
        return suffix or ""

    estimate = int(len(text) * target / total)
    lo, hi = 0, min(estimate + max(estimate // 2, 64), len(text))

    while lo < hi:
        mid = (lo + hi + 1) // 2
        if count_text_tokens(text[:mid], model) <= target:
            lo = mid
        else:
            hi = mid - 1

    pos = text[:lo].rfind(" ")
    if pos <= 0:
        pos = lo
    return text[:pos].rstrip() + suffix
