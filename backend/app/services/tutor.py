"""Tutor service: mode classification, response generation, and SSE streaming.

Design follows docs/ARCHITECTURE.md LLM client pattern:
  - TutorModeClassifier and TutorResponder are injectable Protocol types.
  - Concrete LLM implementations wrap LLMClient.
  - FallbackTutorModeClassifier is a deterministic classifier for local dev.
  - Fake implementations are used in tests (no live LLM calls).

The main entry point for the chat endpoint is stream_chat_response(), an async
generator that yields raw SSE event strings.

On LLM generation failure:
  - An SSE error event is emitted.
  - The session is rolled back; NEITHER the user turn NOR the assistant turn
    is persisted.  (See conversations.py for the documented known deviation.)
  - No partial tokens are emitted after the error event.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.prompts import prompt_registry
from backend.app.models.concept import ConceptNode
from backend.app.models.trail import Trail
from backend.app.schemas.tutor import ConversationMessage, TutorMode
from backend.app.services.conversations import (
    TutorContext,
    TutorSourceMetadata,
    build_tutor_context,
    get_next_turn_index,
    get_or_create_conversation,
    persist_assistant_turn,
    persist_user_turn,
)

if TYPE_CHECKING:
    from backend.app.agents.llm_client import LLMClient
    from backend.app.agents.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)

# Map tutor mode → prompt task name.
_MODE_TO_TASK: dict[TutorMode, str] = {
    "socratic": "tutor_socratic",
    "direct": "tutor_direct",
    "repair": "tutor_repair",
    "quiz_prompt": "tutor_socratic",  # Phase 4A: quiz uses socratic prompt; quiz cards in Phase 5
    "explore": "tutor_explore",
}

_VALID_MODES: frozenset[str] = frozenset(_MODE_TO_TASK)

TutorStreamChunk = tuple[str, str]


# ---------------------------------------------------------------------------
# Deterministic fallback keyword sets (lower-case, substring match)
# ---------------------------------------------------------------------------

_QUIZ_KEYWORDS: frozenset[str] = frozenset(
    [
        "test me",
        "quiz me",
        "i'm ready",
        "i am ready",
        "think i understand",
        "i think i know",
        "ready to test",
    ]
)
_REPAIR_KEYWORDS: frozenset[str] = frozenset(
    [
        "confused",
        "don't understand",
        "do not understand",
        "i thought",
        "isn't it",
        "is not it",
        "mistake",
        "but wait",
    ]
)
_DIRECT_KEYWORDS: frozenset[str] = frozenset(
    [
        "explain",
        "just tell",
        "give me",
        "summarize",
        "summary",
        "tell me",
        "show me an example",
        "give an example",
    ]
)
_EXPLORE_KEYWORDS: frozenset[str] = frozenset(
    [
        "real world",
        "real-world",
        "application",
        "why does",
        "when would",
        "why is it",
        "in practice",
        "why it matters",
        "what's the point",
        "used in",
        "use case",
    ]
)


# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class TutorModeClassifier(Protocol):
    async def classify(self, context: TutorContext) -> TutorMode:
        """Return the tutor mode for the given learner context."""
        ...


@runtime_checkable
class TutorResponder(Protocol):
    def respond_stream(
        self, mode: TutorMode, context: TutorContext
    ) -> AsyncIterator[TutorStreamChunk]:
        """Yield tagged chunks for the tutor response in the given mode."""
        ...


# ---------------------------------------------------------------------------
# Concrete LLM implementations
# ---------------------------------------------------------------------------


class LLMTutorModeClassifier:
    """Classify tutor mode using LLM.  Falls back to 'socratic' on parse errors."""

    def __init__(
        self,
        client: LLMClient,
        registry: PromptRegistry = prompt_registry,
    ) -> None:
        self._client = client
        self._registry = registry

    async def classify(self, context: TutorContext) -> TutorMode:
        summary_text = (
            context.conversation_summary.summary_text
            if context.conversation_summary is not None
            else ""
        )
        recent_turns_text = (
            "\n".join(f"{t.role.upper()}: {t.content}" for t in context.recent_turns) or "none"
        )
        system_prompt = self._registry.render(
            "tutor_mode_classifier",
            {
                "concept_title": context.concept.title,
                "mastery_status": context.mastery_status,
                "conversation_summary": summary_text,
                "recent_turns": recent_turns_text,
            },
        )
        try:
            raw = await self._client.chat(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context.learner_message},
                ],
                temperature=0.1,
                max_tokens=256,
            )
            return _parse_mode_json(raw)
        except Exception:
            logger.warning("Mode classifier LLM call failed; defaulting to socratic")
            return "socratic"


class LLMTutorResponder:
    """Generate a streaming tutor response using LLM."""

    def __init__(
        self,
        client: LLMClient,
        registry: PromptRegistry = prompt_registry,
    ) -> None:
        self._client = client
        self._registry = registry

    async def respond_stream(
        self, mode: TutorMode, context: TutorContext
    ) -> AsyncIterator[TutorStreamChunk]:
        task = _MODE_TO_TASK[mode]
        variables = _context_to_prompt_vars(mode, context)
        system_prompt = self._registry.render(task, variables)
        messages = _build_chat_messages(system_prompt, context.recent_turns, context.learner_message)
        async for kind, chunk in self._client.chat_stream_tagged(
            messages, temperature=0.7, max_tokens=1024
        ):
            yield kind, chunk


# ---------------------------------------------------------------------------
# Deterministic fallback classifier (no LLM needed)
# ---------------------------------------------------------------------------


class FallbackTutorModeClassifier:
    """Keyword-based deterministic mode classifier for local dev and tests."""

    async def classify(self, context: TutorContext) -> TutorMode:
        msg = context.learner_message.lower()

        # Check in priority order: quiz > repair > explore > direct > socratic
        if any(kw in msg for kw in _QUIZ_KEYWORDS):
            return "quiz_prompt"
        if any(kw in msg for kw in _REPAIR_KEYWORDS):
            return "repair"
        if any(kw in msg for kw in _EXPLORE_KEYWORDS):
            return "explore"
        if any(kw in msg for kw in _DIRECT_KEYWORDS):
            return "direct"
        return "socratic"


# ---------------------------------------------------------------------------
# SSE streaming orchestrator
# ---------------------------------------------------------------------------


def _sse(event_type: str, data: dict) -> str:
    """Format a single Server-Sent Event string."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def stream_chat_response(
    session: AsyncSession,
    classifier: TutorModeClassifier,
    responder: TutorResponder,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    message: str,
    conversation_id: uuid.UUID | None,
) -> AsyncIterator[str]:
    """Main SSE generator for the chat endpoint.

    Event order:
      1. mode      — selected tutor mode
      2. thinking* — optional reasoning chunks
      3. token+    — streamed response tokens
      4. done      — assembled ConversationMessage + conversation_id

    On LLM failure:
      - error event is emitted.
      - Session is rolled back; no turns are persisted.
    """
    # 1. Get or create conversation (validates scope).
    try:
        conversation = await get_or_create_conversation(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            conversation_id=conversation_id,
        )
    except LookupError as exc:
        yield _sse("error", {"type": "error", "code": "not_found", "message": str(exc)})
        return

    # 2. Reserve turn indexes.
    user_turn_index = await get_next_turn_index(session, conversation.id)
    assistant_turn_index = user_turn_index + 1

    # 3. Persist user turn (flushed, not yet committed).
    await persist_user_turn(session, conversation.id, message.strip(), user_turn_index)

    # 4. Load trail + concept (already validated, reload from session cache).
    trail = await session.scalar(select(Trail).where(Trail.id == trail_id))
    concept = await session.scalar(select(ConceptNode).where(ConceptNode.id == concept_id))
    if trail is None or concept is None:
        await session.rollback()
        yield _sse(
            "error",
            {"type": "error", "code": "not_found", "message": "Concept context not found"},
        )
        return

    # 5. Assemble tutor context.
    context = await build_tutor_context(
        session,
        conversation=conversation,
        concept=concept,
        trail=trail,
        learner_message=message.strip(),
        user_turn_index=user_turn_index,
    )

    # 6. Classify mode.
    try:
        mode: TutorMode = await classifier.classify(context)
    except Exception as exc:
        logger.warning("Tutor mode classifier failed; defaulting to socratic. Error: %s", exc)
        mode = "socratic"

    # 7. Emit mode event BEFORE tokens.
    yield _sse("mode", {"type": "mode", "mode": mode})

    # 8. Stream response chunks, collecting visible text plus provider-exposed reasoning.
    full_text = ""
    full_reasoning = ""
    try:
        async for kind, chunk in responder.respond_stream(mode, context):
            if kind == "thinking":
                full_reasoning += chunk
                yield _sse("thinking", {"type": "thinking", "content": chunk})
                continue
            full_text += chunk
            yield _sse("token", {"type": "token", "content": chunk})
    except Exception as exc:
        logger.error("Tutor responder failed: %s", exc)
        await session.rollback()
        yield _sse("error", {"type": "error", "code": "llm_error", "message": "Generation failed"})
        return

    # 9. Persist assistant turn and commit transaction.
    assistant_turn = await persist_assistant_turn(
        session,
        conversation.id,
        full_text,
        mode,
        assistant_turn_index,
        reasoning=full_reasoning or None,
    )

    # 10. Emit done event with assembled message.
    msg_schema = ConversationMessage.model_validate(assistant_turn)
    yield _sse(
        "done",
        {
            "type": "done",
            "conversation_id": str(conversation.id),
            "message": msg_schema.model_dump(mode="json"),
        },
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse_mode_json(raw: str) -> TutorMode:
    """Parse classifier JSON; return 'socratic' on any error."""
    try:
        text = raw.strip()
        # Strip markdown fences if the model wrapped the JSON.
        text = re.sub(r"```[a-z]*\n?", "", text).strip()
        data = json.loads(text)
        mode = data.get("mode", "socratic")
        if mode not in _VALID_MODES:
            logger.warning("Unknown mode %r from classifier; falling back to socratic", mode)
            return "socratic"
        return cast(TutorMode, mode)
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Could not parse mode classifier response; falling back to socratic")
        return "socratic"


def _build_chat_messages(
    system_prompt: str,
    recent_turns: list,
    learner_message: str,
) -> list[dict]:
    """Build a properly structured messages array for LLM API calls.

    Structure:
      - system  : full system prompt (persona, concept context, task, guidelines).
      - user /
        assistant: actual conversation history turns in chronological order.
      - user    : the learner's latest message as the final user turn.

    Keeping system instructions in the system role and history as real
    user/assistant messages enables:
      - Prompt caching on the static system message (Anthropic, OpenAI).
      - Correct context window management by the provider.
      - Cleaner separation between instructions and conversational data.
    """
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for turn in recent_turns:
        messages.append({"role": turn.role, "content": turn.content})
    messages.append({"role": "user", "content": learner_message})
    return messages


def _format_sources(sources: list[TutorSourceMetadata]) -> str:
    """Render safe source metadata as a prompt-friendly string.

    Format per source (one bullet per line):
        - <title> (<url>), license: <license>, relation: <relation>

    Only whitelisted fields are exposed.  Raw content is never included.
    """
    if not sources:
        return "none available"
    lines: list[str] = []
    for s in sources:
        url_part = f" ({s.url})" if s.url else ""
        license_part = f", license: {s.license}" if s.license else ", license: unknown"
        lines.append(f"- {s.title}{url_part}{license_part}, relation: {s.relation}")
    return "\n".join(lines)


def _context_to_prompt_vars(mode: TutorMode, context: TutorContext) -> dict:
    """Convert TutorContext into prompt template variables."""
    prereqs = ", ".join(c.title for c in context.prerequisites) or "none"
    contained = ", ".join(c.title for c in context.contained_nodes) or "none"
    containing = ", ".join(c.title for c in context.containing_nodes) or "none"
    app_nodes = ", ".join(c.title for c in context.application_nodes) or "none"

    recent_turns_text = (
        "\n".join(f"{t.role.upper()}: {t.content}" for t in context.recent_turns) or "none"
    )
    summary_text = (
        context.conversation_summary.summary_text
        if context.conversation_summary is not None
        else ""
    )

    variables: dict = {
        "concept": f"{context.concept.title} ({context.concept.concept_level})",
        "concept_level": context.concept.concept_level,
        "prerequisites": prereqs,
        "contained_nodes": contained,
        "containing_nodes": containing,
        "mastery_status": context.mastery_status,
        "bloom_target": context.concept.bloom_level,
        "learning_goal": context.trail.goal,
        "sources": _format_sources(context.sources),
        "conversation_summary": summary_text,
        "recent_turns": recent_turns_text,
        "learner_message": context.learner_message,
    }
    if mode == "explore":
        variables["application_nodes"] = app_nodes

    return variables
