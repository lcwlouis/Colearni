"""Token-aware message trimming for LLM completion calls.

Trims the oldest non-system history messages when the total token count
exceeds a configurable fraction of the model's context window, preserving
the system prefix and the last user message.
"""

from __future__ import annotations

import logging

from core.llm_messages import Message

log = logging.getLogger(__name__)


def trim_messages(
    messages: list[Message],
    model: str,
    *,
    max_fraction: float = 0.8,
) -> list[Message]:
    """Trim oldest non-system messages if total tokens exceed model limit.

    Preserves: all system messages (prefix), the last user message.
    Trims: oldest user/assistant messages in the middle (history).

    Uses ``litellm.token_counter()`` for counting and
    ``litellm.get_max_tokens()`` for limits.  Falls back to no trimming
    if token counting is unavailable.
    """
    if not messages:
        return messages

    try:
        import litellm  # noqa: WPS433 — optional dependency
    except ImportError:
        log.debug("litellm not available; skipping message trimming")
        return messages

    try:
        model_max = int(litellm.get_max_tokens(model) * max_fraction)
    except Exception:
        log.debug("Cannot determine max tokens for %s; skipping trimming", model)
        return messages

    try:
        total = litellm.token_counter(model=model, messages=messages)
    except Exception:
        log.debug("Token counting failed for %s; skipping trimming", model)
        return messages

    if total <= model_max:
        return messages

    # Split into: system_prefix + history + last_user_message
    system_prefix: list[Message] = []
    rest: list[Message] = []

    for msg in messages:
        if msg["role"] == "system" and not rest:
            system_prefix.append(msg)
        else:
            rest.append(msg)

    if len(rest) <= 1:
        # Only the last user message (or nothing) — nothing to trim.
        return messages

    last_user = rest[-1]
    history = rest[:-1]

    # Remove oldest history messages until under limit.
    while history:
        candidate = system_prefix + history + [last_user]
        try:
            total = litellm.token_counter(model=model, messages=candidate)
        except Exception:
            return messages
        if total <= model_max:
            return candidate
        history.pop(0)

    return system_prefix + [last_user]
