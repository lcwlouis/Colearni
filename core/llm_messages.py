"""Typed message list builder for LLM completion calls.

Provides a fluent API for constructing validated ``messages[]`` arrays
that follow the OpenAI / LiteLLM chat-completion contract.  Used by every
LLM call-site in the codebase instead of raw ``list[dict]`` construction.
"""

from __future__ import annotations

from typing import Literal, Sequence, TypedDict

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

MessageRole = Literal["system", "user", "assistant", "tool"]

_CONTEXT_DELIMITER = "---"


class Message(TypedDict, total=False):
    """Single message in an LLM ``messages[]`` array.

    ``role`` and ``content`` are always required at runtime; the remaining
    keys are optional and only used by tool-calling flows.
    """

    role: str  # MessageRole — kept as str for dict compat with SDKs
    content: str
    name: str
    tool_call_id: str


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class MessageBuilder:
    """Fluent builder for constructing validated LLM message lists.

    Usage::

        msgs = (
            MessageBuilder()
            .system("You are a helpful tutor.")
            .context("Document summary: …", label="documents")
            .user("What is recursion?")
            .build()
        )

    Validation rules enforced by :meth:`build`:

    * The list must be non-empty.
    * System messages (if any) must appear before all non-system messages.
    * The final message must have role ``user`` or ``tool``.
    """

    __slots__ = ("_messages",)

    def __init__(self) -> None:
        self._messages: list[Message] = []

    # -- mutators (return self for chaining) --------------------------------

    def system(self, content: str) -> MessageBuilder:
        """Append a ``system`` message.

        System messages should be added before any user/assistant messages.
        """
        if not content:
            return self
        self._messages.append({"role": "system", "content": content})
        return self

    def user(self, content: str) -> MessageBuilder:
        """Append a ``user`` message."""
        if not content:
            return self
        self._messages.append({"role": "user", "content": content})
        return self

    def assistant(self, content: str) -> MessageBuilder:
        """Append an ``assistant`` message."""
        if not content:
            return self
        self._messages.append({"role": "assistant", "content": content})
        return self

    def tool(self, content: str, *, tool_call_id: str) -> MessageBuilder:
        """Append a ``tool`` result message."""
        if not content:
            return self
        self._messages.append(
            {"role": "tool", "content": content, "tool_call_id": tool_call_id},
        )
        return self

    def context(
        self,
        content: str,
        *,
        label: str | None = None,
    ) -> MessageBuilder:
        """Append a context block as a ``system`` message.

        Context blocks carry variable per-turn data (document summaries,
        graph context, assessment history, etc.) that should be separated
        from the stable persona prefix for prompt-caching purposes.

        Parameters
        ----------
        content:
            The context text.
        label:
            Optional human-readable label included as a delimiter header.
        """
        if not content:
            return self
        if label:
            text = f"{_CONTEXT_DELIMITER}\n[{label}]\n{content}\n{_CONTEXT_DELIMITER}"
        else:
            text = content
        self._messages.append({"role": "system", "content": text})
        return self

    def history(
        self,
        turns: Sequence[tuple[str, str]],
    ) -> MessageBuilder:
        """Append chat-history turn pairs as ``user`` / ``assistant`` messages.

        Parameters
        ----------
        turns:
            Sequence of ``(user_text, assistant_text)`` pairs, oldest first.
        """
        for user_text, assistant_text in turns:
            if user_text:
                self._messages.append({"role": "user", "content": user_text})
            if assistant_text:
                self._messages.append(
                    {"role": "assistant", "content": assistant_text},
                )
        return self

    # -- accessors ----------------------------------------------------------

    @property
    def messages(self) -> list[Message]:
        """Return a shallow copy of the internal message list (no validation)."""
        return list(self._messages)

    def __len__(self) -> int:
        return len(self._messages)

    def __bool__(self) -> bool:
        return bool(self._messages)

    # -- build & validate ---------------------------------------------------

    def build(self) -> list[Message]:
        """Validate ordering rules and return the final message list.

        Raises
        ------
        ValueError
            If the message list is empty, system messages appear after
            non-system messages, or the last message is not ``user``/``tool``.
        """
        if not self._messages:
            raise ValueError("MessageBuilder is empty — add at least one message.")

        # System messages must precede all non-system messages.
        seen_non_system = False
        for msg in self._messages:
            if msg["role"] != "system":
                seen_non_system = True
            elif seen_non_system:
                raise ValueError(
                    "System messages must appear before all non-system messages. "
                    f"Found system message after {msg['role']} message."
                )

        last_role = self._messages[-1]["role"]
        if last_role not in ("user", "tool"):
            raise ValueError(
                f"Last message must have role 'user' or 'tool', got '{last_role}'."
            )

        return list(self._messages)


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def quick_messages(system: str, user: str) -> list[Message]:
    """Build a simple 2-message list (system + user).

    This is a drop-in replacement for the current inline pattern::

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
    """
    return MessageBuilder().system(system).user(user).build()
