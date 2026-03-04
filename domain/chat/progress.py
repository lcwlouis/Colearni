"""Progress callback protocol for chat generation lifecycle."""

from __future__ import annotations

from typing import Protocol

from core.schemas.chat import ChatPhase


class ProgressSink(Protocol):
    """Receives phase transitions during chat response generation.

    Implementations may buffer SSE events, log, or no-op.
    """

    def on_phase(self, phase: ChatPhase) -> None:
        """Signal that the orchestrator has entered *phase*."""


class NoOpProgressSink:
    """Default sink used by the blocking /chat/respond path."""

    def on_phase(self, phase: ChatPhase) -> None:  # noqa: ARG002
        pass


_NOOP_SINK = NoOpProgressSink()


def noop_sink() -> NoOpProgressSink:
    """Return the shared no-op progress sink."""
    return _NOOP_SINK
