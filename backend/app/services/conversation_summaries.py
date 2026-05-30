from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.prompts import prompt_registry
from backend.app.models.conversation import ConversationSummary, ConversationTurn

if TYPE_CHECKING:
    from backend.app.agents.llm_client import LLMClient
    from backend.app.agents.prompts.registry import PromptRegistry

_MAX_SUMMARY_CHARS = 3000
_TURN_SNIPPET_CHARS = 800

# Defaults used when callers don't override. The char budget corresponds to
# roughly 15 k tokens (≈4 chars/token), well within a 128 k context model's
# history allocation. The batch floor prevents one-turn re-summarization.
_DEFAULT_HISTORY_CHAR_BUDGET = 60_000
_DEFAULT_SUMMARY_BATCH_SIZE = 5


class ConversationSummaryError(Exception):
    pass


@runtime_checkable
class ConversationSummarizer(Protocol):
    async def summarize(self, *, previous_summary: str, new_turns: str) -> str: ...


class LLMConversationSummarizer:
    """LLM-backed conversation summarizer for Phase 13 tutor context."""

    def __init__(self, client: LLMClient, registry: PromptRegistry = prompt_registry) -> None:
        self._client = client
        self._registry = registry

    async def summarize(self, *, previous_summary: str, new_turns: str) -> str:
        prompt = self._registry.render(
            "conversation_summary",
            {
                "previous_summary": previous_summary or "No previous summary.",
                "new_turns": new_turns,
            },
            version=1,
        )
        raw = await self._client.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=700,
        )
        return _clean_summary(raw)


async def maybe_generate_conversation_summary(
    session: AsyncSession,
    summarizer: ConversationSummarizer,
    *,
    conversation_id: uuid.UUID,
    through_turn_index: int,
    recent_visible_turns_limit: int,
    history_char_budget: int = _DEFAULT_HISTORY_CHAR_BUDGET,
    batch_size: int = _DEFAULT_SUMMARY_BATCH_SIZE,
) -> ConversationSummary | None:
    """Create an LLM summary for older visible turns, bounded and idempotent.

    Summaries cover only visible user/assistant turns that have fallen outside
    the raw recent-turn window. Hidden tool calls/results and provider reasoning
    are never sent to the summarizer.

    Triggering uses a character-budget threshold rather than a raw turn count so
    that short conversations never pay the summarization cost, while long
    conversations are compressed before the context window fills up.  A batch
    floor (batch_size) prevents one-turn-at-a-time re-summarization: we wait
    until at least that many new un-covered turns have accumulated before
    issuing another LLM summary call.
    """
    visible_turns = list(
        await session.scalars(
            select(ConversationTurn)
            .where(
                ConversationTurn.conversation_id == conversation_id,
                ConversationTurn.kind == "visible",
                ConversationTurn.turn_index <= through_turn_index,
            )
            .order_by(ConversationTurn.turn_index.asc())
        )
    )

    # Character-budget check: only summarize when the total history is large
    # enough to warrant compression.  This replaces the old turn-count trigger
    # so short conversations are never summarized unnecessarily.
    total_chars = sum(len(t.content) for t in visible_turns)
    if total_chars <= history_char_budget:
        return None

    # We must have at least one turn outside the verbatim window to cover.
    if len(visible_turns) <= recent_visible_turns_limit:
        return None

    turns_to_cover = visible_turns[:-recent_visible_turns_limit]
    covered_to = turns_to_cover[-1].turn_index

    existing = await session.scalar(
        select(ConversationSummary).where(
            ConversationSummary.conversation_id == conversation_id,
            ConversationSummary.turns_covered_to == covered_to,
        )
    )
    if existing is not None:
        return existing

    previous = await session.scalar(
        select(ConversationSummary)
        .where(
            ConversationSummary.conversation_id == conversation_id,
            ConversationSummary.turns_covered_to < covered_to,
        )
        .order_by(ConversationSummary.turns_covered_to.desc())
        .limit(1)
    )
    start_after = previous.turns_covered_to if previous is not None else -1
    new_turns = [turn for turn in turns_to_cover if turn.turn_index > start_after]
    if not new_turns:
        return previous

    # Batch floor: don't fire a new LLM call for just one or two new turns.
    # Return the previous summary until the batch threshold is met.
    if len(new_turns) < batch_size:
        return previous

    summary_text = await summarizer.summarize(
        previous_summary=previous.summary_text if previous else "",
        new_turns=_format_turns(new_turns),
    )
    summary = ConversationSummary(
        conversation_id=conversation_id,
        turns_covered_to=covered_to,
        summary_text=summary_text,
    )
    session.add(summary)
    await session.flush()
    return summary


async def delete_stale_conversation_summaries(
    session: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    from_turn_index: int,
) -> None:
    """Delete summaries that include edited/deleted conversation content."""
    await session.execute(
        delete(ConversationSummary).where(
            ConversationSummary.conversation_id == conversation_id,
            ConversationSummary.turns_covered_to >= from_turn_index,
        )
    )


def _format_turns(turns: list[ConversationTurn]) -> str:
    lines: list[str] = []
    for turn in turns:
        role = "Learner" if turn.role == "user" else "Tutor"
        lines.append(f"[{turn.turn_index}] {role}: {_excerpt(turn.content, _TURN_SNIPPET_CHARS)}")
    return "\n".join(lines)


def _clean_summary(raw: str) -> str:
    cleaned = raw.strip().strip("`").strip()
    if cleaned.startswith("summary:"):
        cleaned = cleaned.removeprefix("summary:").strip()
    if not cleaned:
        raise ConversationSummaryError("conversation_summary returned an empty summary")
    if len(cleaned) <= _MAX_SUMMARY_CHARS:
        return cleaned
    return f"{cleaned[: _MAX_SUMMARY_CHARS - 1].rstrip()}…"


def _excerpt(text: str, max_chars: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return f"{cleaned[: max_chars - 1].rstrip()}…"
