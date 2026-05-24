"""Tutor service: single-agent response generation, tool-gated continuations, and SSE streaming.

The Phase 5 tutor flow uses one base system prompt for normal Socratic / repair /
bounded explore behaviour. When the model decides it needs a mastery-gated mode
(`direct` or `free_explore`), it requests `get_tutor_instructions(mode)` via a
structured control header. The service resolves that request, appends synthetic
tool-call history, and continues the same turn with a second model call.

The chat endpoint still exposes one streamed SSE response to the frontend:

  1. mode      — selected tutor mode
  2. thinking* — optional provider reasoning chunks
  3. token+    — streamed visible response tokens
  4. done      — assembled ConversationMessage + conversation_id

If generation fails, the session is rolled back and no turns are persisted.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.prompts import prompt_registry
from backend.app.agents.provider_tools import (
    NormalizedToolCall,
    NormalizedToolResult,
    ProviderToolDefinition,
    normalize_tool_call,
)
from backend.app.schemas.tutor import ConversationMessage, TutorMode
from backend.app.services.conversations import (
    TutorContext,
    TutorSourceMetadata,
    build_tutor_context,
    get_next_turn_index,
    get_or_create_conversation,
    persist_assistant_turn,
    persist_tool_turn,
    persist_user_turn,
    validate_concept_scope,
)
from backend.app.services.mastery import mark_learning_from_tutor_turn

if TYPE_CHECKING:
    from backend.app.agents.llm_client import LLMClient
    from backend.app.agents.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)

_QUIZ_KEYWORDS: frozenset[str] = frozenset(
    {
        "test me",
        "quiz me",
        "i'm ready",
        "i am ready",
        "ready to test",
        "ready for a quiz",
    }
)
_REPAIR_KEYWORDS: frozenset[str] = frozenset(
    {
        "confused",
        "don't understand",
        "do not understand",
        "i thought",
        "isn't it",
        "is not it",
        "mistake",
        "but wait",
    }
)
_DIRECT_KEYWORDS: frozenset[str] = frozenset(
    {
        "explain",
        "just tell",
        "give me",
        "summarise",
        "summarize",
        "summary",
        "tell me",
        "show me an example",
        "give an example",
    }
)
_EXPLORE_KEYWORDS: frozenset[str] = frozenset(
    {
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
    }
)

_VALID_MODES: frozenset[str] = frozenset(
    {"socratic", "direct", "repair", "quiz_prompt", "explore", "free_explore"}
)
_VALID_STATUSES: frozenset[str] = frozenset(
    {
        "thinking",
        "calling_tool",
        "tool_called",
        "tool_complete",
        "responding",
        "retrying_without_thinking",
    }
)
_TOOL_GATED_MODES: frozenset[str] = frozenset({"direct", "free_explore"})
_PROMPT_MODE_TASKS: dict[str, str] = {
    "direct": "tutor_direct_instructions",
    "free_explore": "tutor_free_explore_instructions",
}
_MASTERED_ONLY_TOOL_MODES: frozenset[str] = frozenset({"direct", "free_explore"})
_TUTOR_INSTRUCTIONS_TOOL = ProviderToolDefinition(
    name="get_tutor_instructions",
    description="Return internal continuation instructions for mastery-gated tutor modes.",
    parameters={
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": sorted(_TOOL_GATED_MODES)},
        },
        "required": ["mode"],
        "additionalProperties": False,
    },
    public_argument_fields=("mode",),
)
_CONTROL_MODE_RE = re.compile(r'^<mode\s+name="([a-z_]+)"\s*/?>$')
_CONTROL_TOOL_RE = re.compile(
    r'^<tool\s+name="get_tutor_instructions"\s+mode="([a-z_]+)"\s*/?>$'
)
_QUESTION_SENTENCE_START_RE = re.compile(
    r'(^|[.!?\n:;]\s+)(what|why|how|which|when|where|who|whom|whose|can|could|would|should|do|does|did|is|are|am|was|were|have|has|had)\b',
    re.IGNORECASE,
)

TutorStreamChunk = tuple[str, str]


@dataclass(frozen=True)
class _ToolInstructionResult:
    requested_mode: str
    final_mode: TutorMode
    content: str
    normalized_call: NormalizedToolCall | None = None
    normalized_result: NormalizedToolResult | None = None


@dataclass(frozen=True)
class _ParsedControl:
    kind: str
    value: str
    remainder: str


@dataclass(frozen=True)
class _PreparedStream:
    mode: TutorMode
    initial_chunks: tuple[TutorStreamChunk, ...]
    stream: AsyncIterator[TutorStreamChunk]


@runtime_checkable
class TutorAgent(Protocol):
    def respond_stream(self, context: TutorContext) -> AsyncIterator[TutorStreamChunk]:
        """Yield a mixed stream of mode, reasoning, token, and tool events."""
        ...


class FallbackTutorModeClassifier:
    """Compatibility helper for tests and local deterministic mode checks."""

    async def classify(self, context: TutorContext) -> TutorMode:
        message = context.learner_message.lower()
        if any(keyword in message for keyword in _QUIZ_KEYWORDS):
            return "quiz_prompt"
        if any(keyword in message for keyword in _REPAIR_KEYWORDS):
            return "repair"
        if any(keyword in message for keyword in _EXPLORE_KEYWORDS):
            return "explore"
        if any(keyword in message for keyword in _DIRECT_KEYWORDS):
            return "direct"
        return "socratic"


class LLMTutorAgent:
    """LLM-backed tutor agent with service-level tool continuation."""

    def __init__(
        self,
        client: LLMClient,
        registry: PromptRegistry = prompt_registry,
        max_tokens: int = 1024,
    ) -> None:
        self._client = client
        self._registry = registry
        self._max_tokens = max(256, max_tokens)

    async def respond_stream(self, context: TutorContext) -> AsyncIterator[TutorStreamChunk]:
        prompt_vars = _context_to_base_prompt_vars(context)
        system_prompt = self._registry.render("tutor_base", prompt_vars)
        messages = _build_chat_messages(
            system_prompt,
            context.recent_turns,
            context.learner_message,
        )

        raw_stream = self._client_chat_stream_tagged(
            messages,
            temperature=0.4,
            max_tokens=self._max_tokens,
        )
        buffered_text = ""
        emitted_first_pass_thinking_status = False

        async for kind, chunk in raw_stream:
            if kind == "thinking":
                if not emitted_first_pass_thinking_status:
                    yield ("status", "thinking")
                    emitted_first_pass_thinking_status = True
                yield ("thinking", chunk)
                continue

            buffered_text += chunk
            parsed = _parse_control_from_buffer(buffered_text)
            if parsed is None:
                continue

            mode = _control_value_to_mode(parsed)
            if mode is None:
                mode = "socratic"

            if mode in _TOOL_GATED_MODES:
                async for event in self._stream_tool_continuation(mode, context, messages):
                    yield event
                return

            yield ("mode", mode)
            remainder = parsed.remainder.lstrip("\n")
            if remainder:
                yield ("text", remainder)
            async for next_kind, next_chunk in raw_stream:
                if next_kind == "thinking":
                    if not emitted_first_pass_thinking_status:
                        yield ("status", "thinking")
                        emitted_first_pass_thinking_status = True
                    yield ("thinking", next_chunk)
                else:
                    yield ("text", next_chunk)
            return

        parsed = _parse_control_eof(buffered_text)
        if parsed is not None:
            mode = _control_value_to_mode(parsed)
            if mode is not None:
                if mode in _TOOL_GATED_MODES:
                    async for event in self._stream_tool_continuation(mode, context, messages):
                        yield event
                    return
                yield ("mode", mode)
                remainder = parsed.remainder.lstrip("\n")
                if remainder:
                    yield ("text", remainder)
                return

        if emitted_first_pass_thinking_status and not buffered_text.strip():
            async for event in self._retry_first_pass_without_thinking(messages, context):
                yield event
            return

        yield ("mode", "socratic")
        if buffered_text:
            yield ("text", buffered_text)

    def _client_chat_stream_tagged(
        self,
        messages: list[dict],
        *,
        temperature: float,
        max_tokens: int,
        thinking: bool | None = None,
    ) -> AsyncIterator[TutorStreamChunk]:
        kwargs: dict[str, object] = {"temperature": temperature, "max_tokens": max_tokens}
        if thinking is not None:
            kwargs["thinking"] = thinking
        return self._client.chat_stream_tagged(messages, **kwargs)

    async def _stream_tool_continuation(
        self,
        requested_mode: str,
        context: TutorContext,
        messages: list[dict],
    ) -> AsyncIterator[TutorStreamChunk]:
        tool_result = self._get_tutor_instructions(requested_mode, context)
        tool_call = _tool_call_content(tool_result.requested_mode)
        tool_message = _tool_result_content(tool_result)
        yield ("status", "calling_tool")
        yield ("tool_call", tool_call)
        yield ("status", "tool_called")
        yield ("tool_result", tool_message)
        yield ("status", "tool_complete")
        yield ("mode", tool_result.final_mode)

        continuation_messages = messages + [
            {"role": "assistant", "content": tool_call},
            {"role": "assistant", "content": tool_message},
        ]
        continuation_stream = self._chat_stream_with_empty_retry(
            continuation_messages,
            temperature=0.4,
            max_tokens=self._max_tokens,
        )

        # Locked direct requests must stay purely Socratic, even if the
        # continuation tries to slip in a partial summary before a question.
        if _should_buffer_locked_socratic_fallback(tool_result, context):
            buffered_text = ""
            emitted_continuation_thinking_status = False
            async for kind, chunk in continuation_stream:
                if kind == "status":
                    yield ("status", chunk)
                elif kind == "thinking":
                    if not emitted_continuation_thinking_status:
                        yield ("status", "thinking")
                        emitted_continuation_thinking_status = True
                    yield ("thinking", chunk)
                else:
                    buffered_text += chunk

            yield ("text", _coerce_locked_socratic_reply(buffered_text, context))
            return

        emitted_continuation_thinking_status = False
        async for kind, chunk in continuation_stream:
            if kind == "status":
                yield ("status", chunk)
            elif kind == "thinking":
                if not emitted_continuation_thinking_status:
                    yield ("status", "thinking")
                    emitted_continuation_thinking_status = True
                yield ("thinking", chunk)
            else:
                yield ("text", chunk)

    async def _chat_stream_with_empty_retry(
        self,
        messages: list[dict],
        *,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[TutorStreamChunk]:
        saw_text = False
        saw_thinking = False
        async for kind, chunk in self._client_chat_stream_tagged(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if kind == "thinking" and chunk:
                saw_thinking = True
            elif chunk.strip():
                saw_text = True
            yield (kind, chunk)

        if saw_text or not saw_thinking:
            return

        yield ("status", "retrying_without_thinking")
        async for kind, chunk in self._client_chat_stream_tagged(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            thinking=False,
        ):
            yield (kind, chunk)

    async def _retry_first_pass_without_thinking(
        self,
        messages: list[dict],
        context: TutorContext,
    ) -> AsyncIterator[TutorStreamChunk]:
        yield ("status", "retrying_without_thinking")
        first_pass = await self._prepare_first_pass(messages, thinking=False)
        if first_pass.mode in _TOOL_GATED_MODES:
            async for event in self._stream_tool_continuation(first_pass.mode, context, messages):
                yield event
            return

        yield ("mode", first_pass.mode)
        for kind, chunk in first_pass.initial_chunks:
            if kind == "thinking":
                yield ("thinking", chunk)
            else:
                yield ("text", chunk)
        async for kind, chunk in first_pass.stream:
            if kind == "thinking":
                yield ("thinking", chunk)
            else:
                yield ("text", chunk)

    async def _prepare_first_pass(
        self,
        messages: list[dict],
        *,
        thinking: bool | None = None,
    ) -> _PreparedStream:
        raw_stream = self._client_chat_stream_tagged(
            messages,
            temperature=0.4,
            max_tokens=self._max_tokens,
            thinking=thinking,
        )
        buffered_text = ""
        initial_chunks: list[TutorStreamChunk] = []

        async for kind, chunk in raw_stream:
            if kind == "thinking":
                initial_chunks.append(("thinking", chunk))
                continue

            buffered_text += chunk
            parsed = _parse_control_from_buffer(buffered_text)
            if parsed is None:
                continue

            mode = _control_value_to_mode(parsed)
            if mode is None:
                return _PreparedStream(
                    mode="socratic",
                    initial_chunks=_append_text_chunk(initial_chunks, buffered_text),
                    stream=_empty_stream(),
                )

            remainder = parsed.remainder.lstrip("\n")
            return _PreparedStream(
                mode=mode,
                initial_chunks=_append_text_chunk(initial_chunks, remainder),
                stream=_continue_text_stream(raw_stream),
            )

        parsed = _parse_control_eof(buffered_text)
        if parsed is not None:
            mode = _control_value_to_mode(parsed)
            if mode is not None:
                return _PreparedStream(
                    mode=mode,
                    initial_chunks=_append_text_chunk(
                        initial_chunks,
                        parsed.remainder.lstrip("\n"),
                    ),
                    stream=_empty_stream(),
                )

        return _PreparedStream(
            mode="socratic",
            initial_chunks=_append_text_chunk(initial_chunks, buffered_text),
            stream=_empty_stream(),
        )

    def _get_tutor_instructions(
        self,
        requested_mode: str,
        context: TutorContext,
    ) -> _ToolInstructionResult:
        tool_call = _normalize_tutor_instruction_request(requested_mode)
        if not tool_call.is_valid:
            content = _wrap_tool_result(
                "socratic",
                (
                    "Tool arguments were invalid. Stay Socratic, ask one focused question, "
                    "and do not mention internal tooling."
                ),
            )
            return _ToolInstructionResult(
                requested_mode="socratic",
                final_mode="socratic",
                content=content,
                normalized_call=tool_call,
                normalized_result=NormalizedToolResult(
                    call_id=tool_call.call_id,
                    name=tool_call.name,
                    content=content,
                    provider=tool_call.provider,
                    is_error=True,
                    public_preview={"status": "invalid_arguments", "mode": "unknown"},
                ),
            )

        requested_mode = str(tool_call.arguments["mode"])
        if requested_mode not in _TOOL_GATED_MODES:
            content = (
                "<tool_result name=\"get_tutor_instructions\" mode=\"socratic\">\n"
                "Unsupported gated mode request. Stay Socratic, ask one focused question, "
                "and do not mention internal tooling.\n"
                "</tool_result>"
            )
            return _ToolInstructionResult(
                requested_mode=requested_mode,
                final_mode="socratic",
                content=content,
                normalized_call=tool_call,
                normalized_result=NormalizedToolResult(
                    call_id=tool_call.call_id,
                    name=tool_call.name,
                    content=content,
                    provider=tool_call.provider,
                    is_error=True,
                    public_preview={"status": "received", "mode": "socratic"},
                ),
            )

        if (
            requested_mode in _MASTERED_ONLY_TOOL_MODES
            and context.mastery_status != "mastered"
        ):
            fallback_mode: TutorMode = "explore" if requested_mode == "free_explore" else "socratic"
            denial = self._registry.render(
                "tutor_locked_mode",
                {
                    **_context_to_base_prompt_vars(context),
                    "requested_mode": requested_mode,
                    "fallback_mode": fallback_mode,
                    "mastery_status": context.mastery_status,
                },
            )
            content = _wrap_tool_result(requested_mode, denial)
            return _ToolInstructionResult(
                requested_mode=requested_mode,
                final_mode=fallback_mode,
                content=content,
                normalized_call=tool_call,
                normalized_result=NormalizedToolResult(
                    call_id=tool_call.call_id,
                    name=tool_call.name,
                    content=content,
                    provider=tool_call.provider,
                    public_preview={"status": "received", "mode": requested_mode},
                ),
            )

        prompt_task = _PROMPT_MODE_TASKS[requested_mode]
        instructions = self._registry.render(prompt_task, _context_to_base_prompt_vars(context))
        content = _wrap_tool_result(requested_mode, instructions)
        return _ToolInstructionResult(
            requested_mode=requested_mode,
            final_mode=requested_mode,  # type: ignore[arg-type]
            content=content,
            normalized_call=tool_call,
            normalized_result=NormalizedToolResult(
                call_id=tool_call.call_id,
                name=tool_call.name,
                content=content,
                provider=tool_call.provider,
                public_preview={"status": "received", "mode": requested_mode},
            ),
        )


def _sse(event_type: str, data: dict) -> str:
    """Format a single Server-Sent Event string."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


async def stream_chat_response(
    session: AsyncSession,
    agent: TutorAgent,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    message: str,
    conversation_id: uuid.UUID | None,
) -> AsyncIterator[str]:
    """Main SSE generator for the chat endpoint."""
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

    trail, concept = await validate_concept_scope(
        session,
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=concept_id,
    )

    mastery_state = await mark_learning_from_tutor_turn(
        session,
        workspace_id=workspace_id,
        concept=concept,
    )

    user_turn_index = await get_next_turn_index(session, conversation.id)
    await persist_user_turn(session, conversation.id, message.strip(), user_turn_index)

    context = await build_tutor_context(
        session,
        conversation=conversation,
        concept=concept,
        trail=trail,
        learner_message=message.strip(),
        user_turn_index=user_turn_index,
    )

    mode: TutorMode | None = None
    full_text = ""
    full_reasoning = ""
    reasoning_parts: list[dict] = []
    tool_turns: list[tuple[str, str, str, str | None]] = []
    emitted_response_status = False

    try:
        async for kind, chunk in agent.respond_stream(context):
            if kind == "status":
                if chunk == "responding":
                    emitted_response_status = True
                status = chunk if chunk in _VALID_STATUSES else "thinking"
                if status != "responding":
                    reasoning_parts.append({"kind": "status", "status": status})
                yield _sse("status", {"type": "status", "status": status})
                continue
            if kind == "tool_call":
                tool_call = _normalize_tutor_instruction_content(chunk)
                tool_mode = _safe_tool_mode(
                    str(tool_call.arguments.get("mode")) if tool_call.is_valid else None
                )
                tool_turns.append(("assistant", "tool_call", chunk, tool_mode))
                reasoning_parts.append(
                    {
                        "kind": "tool_call",
                        "name": "get_tutor_instructions",
                        "mode": tool_mode,
                    }
                )
                yield _sse(
                    "tool_call",
                    {
                        "type": "tool_call",
                        "name": "get_tutor_instructions",
                        "mode": tool_mode,
                    },
                )
                continue
            if kind == "tool_result":
                tool_mode = _safe_tool_mode(_extract_tool_mode(chunk))
                preview = _tool_result_preview(chunk)
                tool_turns.append(("tool", "tool_result", chunk, tool_mode))
                reasoning_parts.append(
                    {
                        "kind": "tool_result",
                        "name": "get_tutor_instructions",
                        "mode": tool_mode,
                        "result": preview,
                    }
                )
                yield _sse(
                    "tool_result",
                    {
                        "type": "tool_result",
                        "name": "get_tutor_instructions",
                        "mode": tool_mode,
                        "result": preview,
                    },
                )
                continue
            if kind == "mode":
                parsed_mode = chunk if chunk in _VALID_MODES else "socratic"
                mode = parsed_mode  # type: ignore[assignment]
                yield _sse("mode", {"type": "mode", "mode": mode})
                continue
            if kind == "thinking":
                full_reasoning += chunk
                if reasoning_parts and reasoning_parts[-1].get("kind") == "thinking":
                    reasoning_parts[-1]["text"] = f"{reasoning_parts[-1].get('text', '')}{chunk}"
                else:
                    reasoning_parts.append({"kind": "thinking", "text": chunk})
                yield _sse("thinking", {"type": "thinking", "content": chunk})
                continue
            visible_chunk = _strip_control_prefix(chunk)
            full_text += visible_chunk
            if not emitted_response_status:
                yield _sse("status", {"type": "status", "status": "responding"})
                emitted_response_status = True
            if visible_chunk:
                yield _sse("token", {"type": "token", "content": visible_chunk})
    except Exception as exc:
        logger.error("Tutor agent failed: %s", exc)
        await session.rollback()
        yield _sse("error", {"type": "error", "code": "llm_error", "message": "Generation failed"})
        return

    if not full_text.strip() and full_reasoning.strip():
        logger.warning("Tutor generation ended with reasoning but no visible text")
        await session.rollback()
        yield _sse(
            "error",
            {
                "type": "error",
                "code": "empty_completion",
                "message": "Generation ended before a visible tutor response was produced",
            },
        )
        return

    if mode is None:
        mode = "socratic"

    next_turn_index = user_turn_index + 1
    for role, kind, content, tool_mode in tool_turns:
        await persist_tool_turn(
            session,
            conversation.id,
            role=role,
            kind=kind,
            content=content,
            turn_index=next_turn_index,
            mode=tool_mode,
        )
        next_turn_index += 1

    assistant_turn = await persist_assistant_turn(
        session,
        conversation.id,
        full_text,
        mode,
        next_turn_index,
        reasoning=full_reasoning or None,
        reasoning_parts=reasoning_parts or None,
    )

    msg_schema = ConversationMessage.model_validate(assistant_turn)
    yield _sse(
        "done",
        {
            "type": "done",
            "conversation_id": str(conversation.id),
            "message": msg_schema.model_dump(mode="json"),
            "mastery_update": {
                "concept_id": str(mastery_state.concept_id),
                "status": mastery_state.status,
                "score": mastery_state.score,
            },
        },
    )


async def _continue_text_stream(
    stream: AsyncIterator[TutorStreamChunk],
) -> AsyncIterator[TutorStreamChunk]:
    async for kind, chunk in stream:
        if kind == "thinking":
            yield ("thinking", chunk)
        else:
            yield ("text", chunk)


def _append_text_chunk(chunks: list[TutorStreamChunk], text: str) -> tuple[TutorStreamChunk, ...]:
    return tuple(chunks + ([("text", text)] if text else []))


async def _empty_stream() -> AsyncIterator[TutorStreamChunk]:
    if False:
        yield ("text", "")


def _should_buffer_locked_socratic_fallback(
    result: _ToolInstructionResult,
    context: TutorContext,
) -> bool:
    return (
        result.requested_mode == "direct"
        and result.final_mode == "socratic"
        and context.mastery_status != "mastered"
    )


def _coerce_locked_socratic_reply(text: str, context: TutorContext) -> str:
    cleaned = _strip_control_prefix(text).strip()
    question = _extract_focused_question(cleaned)
    if question is not None:
        return question
    return _default_locked_socratic_question(context)


def _extract_focused_question(text: str) -> str | None:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return None

    question_end = normalized.rfind("?")
    if question_end == -1:
        return None

    question_window = normalized[: question_end + 1]
    matches = list(_QUESTION_SENTENCE_START_RE.finditer(question_window))
    if matches:
        start = matches[-1].start(2)
        candidate = question_window[start : question_end + 1]
    elif len(question_window.split()) <= 6:
        candidate = question_window
    else:
        return None

    candidate = candidate.strip(" \t\r\n\"'`*-")
    if not candidate or not candidate.endswith("?"):
        return None
    if len(candidate.split()) > 28:
        return None
    if candidate[0].islower():
        candidate = candidate[0].upper() + candidate[1:]
    return candidate


def _default_locked_socratic_question(context: TutorContext) -> str:
    learner_message = context.learner_message.lower()
    concept_title = context.concept.title

    if "example" in learner_message:
        return f"What example of {concept_title} comes to mind first?"
    if any(
        keyword in learner_message
        for keyword in ("summarize", "summarise", "summary", "theme", "themes", "topic", "topics")
    ):
        return f"What do you think are the main topics or themes within {concept_title}?"
    if any(
        keyword in learner_message
        for keyword in ("why", "real world", "real-world", "application", "used in", "use case")
    ):
        return f"Where do you think {concept_title} shows up in practice?"
    return f"What do you already understand about {concept_title}?"


def _parse_control_from_buffer(buffer: str) -> _ParsedControl | None:
    newline = buffer.find("\n")
    if newline == -1:
        return None

    line = buffer[:newline].strip()
    remainder = buffer[newline + 1 :]

    tool_match = _CONTROL_TOOL_RE.match(line)
    if tool_match:
        return _ParsedControl(kind="tool", value=tool_match.group(1), remainder=remainder)

    mode_match = _CONTROL_MODE_RE.match(line)
    if mode_match:
        return _ParsedControl(kind="mode", value=mode_match.group(1), remainder=remainder)

    return _ParsedControl(kind="fallback", value="socratic", remainder=buffer)


def _parse_control_eof(buffer: str) -> _ParsedControl | None:
    line = buffer.strip()
    if not line:
        return None

    tool_match = _CONTROL_TOOL_RE.match(line)
    if tool_match:
        return _ParsedControl(kind="tool", value=tool_match.group(1), remainder="")

    mode_match = _CONTROL_MODE_RE.match(line)
    if mode_match:
        return _ParsedControl(kind="mode", value=mode_match.group(1), remainder="")

    return None


def _strip_control_prefix(text: str) -> str:
    """Remove leaked leading control lines from visible tutor text."""
    if not text:
        return ""

    cleaned = text
    while True:
        lines = cleaned.split("\n", 1)
        first_line = lines[0].strip()
        if _CONTROL_MODE_RE.match(first_line) or _CONTROL_TOOL_RE.match(first_line):
            cleaned = lines[1] if len(lines) > 1 else ""
            continue
        return cleaned


def _control_value_to_mode(parsed: _ParsedControl) -> TutorMode | None:
    if parsed.kind == "fallback":
        return "socratic"
    if parsed.value not in _VALID_MODES:
        logger.warning("Unknown tutor mode %r; defaulting to socratic", parsed.value)
        return "socratic"
    return parsed.value  # type: ignore[return-value]


def _parse_mode_json(raw: str) -> TutorMode:
    """Compatibility JSON parser retained for unit tests."""
    try:
        text = raw.strip()
        text = re.sub(r"```[a-z]*\n?", "", text).strip()
        data = json.loads(text)
        mode = data.get("mode", "socratic")
        if mode not in _VALID_MODES:
            logger.warning("Unknown mode %r from classifier JSON; defaulting to socratic", mode)
            return "socratic"
        return mode
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Could not parse mode JSON; defaulting to socratic")
        return "socratic"


def _build_chat_messages(
    system_prompt: str,
    recent_turns: list,
    learner_message: str,
) -> list[dict]:
    """Build a provider-neutral message array.

    Internal tool turns are replayed as tagged assistant messages so the same
    semantic history can be reused across providers without relying on provider-
    specific tool-call wire formats.
    """
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for turn in recent_turns:
        if turn.role == "tool" or getattr(turn, "kind", "visible") == "tool_result":
            messages.append(
                {
                    "role": "assistant",
                    "content": _tool_result_content(
                        _ToolInstructionResult(
                            requested_mode=turn.mode or "socratic",
                            final_mode=(turn.mode or "socratic"),  # type: ignore[arg-type]
                            content=turn.content,
                        )
                    )
                    if not turn.content.startswith("<tool_result")
                    else turn.content,
                }
            )
            continue
        messages.append({"role": turn.role, "content": turn.content})
    messages.append({"role": "user", "content": learner_message})
    return messages


def _format_sources(sources: list[TutorSourceMetadata]) -> str:
    """Render safe source metadata as a prompt-friendly string."""
    if not sources:
        return "none available"
    lines: list[str] = []
    for source in sources:
        url_part = f" ({source.url})" if source.url else ""
        license_part = f", license: {source.license}" if source.license else ", license: unknown"
        lines.append(f"- {source.title}{url_part}{license_part}, relation: {source.relation}")
    return "\n".join(lines)


def _context_to_base_prompt_vars(context: TutorContext) -> dict[str, str]:
    recent_turns_text = (
        "\n".join(f"{turn.role.upper()}: {turn.content}" for turn in context.recent_turns) or "none"
    )
    summary_text = (
        context.conversation_summary.summary_text
        if context.conversation_summary is not None
        else ""
    )

    return {
        "concept": f"{context.concept.title} ({context.concept.concept_level})",
        "concept_level": context.concept.concept_level,
        "prerequisites": ", ".join(node.title for node in context.prerequisites) or "none",
        "contained_nodes": ", ".join(node.title for node in context.contained_nodes) or "none",
        "containing_nodes": ", ".join(node.title for node in context.containing_nodes) or "none",
        "application_nodes": ", ".join(node.title for node in context.application_nodes) or "none",
        "related_nodes": ", ".join(node.title for node in context.related) or "none",
        "mastery_status": context.mastery_status,
        "bloom_target": context.concept.bloom_level,
        "learning_goal": context.trail.goal,
        "sources": _format_sources(context.sources),
        "conversation_summary": summary_text,
        "recent_turns": recent_turns_text,
        "learner_message": context.learner_message,
    }


def _context_to_prompt_vars(mode: TutorMode, context: TutorContext) -> dict[str, str]:
    """Compatibility helper retained for existing unit tests."""
    variables = _context_to_base_prompt_vars(context)
    if mode not in {"explore", "free_explore"}:
        variables.pop("application_nodes", None)
    return variables


def _normalize_tutor_instruction_request(mode: str) -> NormalizedToolCall:
    return normalize_tool_call(
        call_id=f"get_tutor_instructions:{mode}",
        name="get_tutor_instructions",
        raw_arguments={"mode": mode},
        provider="colearni_compat",
        definition=_TUTOR_INSTRUCTIONS_TOOL,
    )


def _normalize_tutor_instruction_content(content: str) -> NormalizedToolCall:
    return _normalize_tutor_instruction_request(_extract_tool_mode(content) or "")


def _tool_call_content(mode: str) -> str:
    return f'<tool name="get_tutor_instructions" mode="{mode}" />'


def _wrap_tool_result(mode: str, instructions: str) -> str:
    return (
        f'<tool_result name="get_tutor_instructions" mode="{mode}">\n'
        f"{instructions.strip()}\n"
        "</tool_result>"
    )


def _tool_result_content(result: _ToolInstructionResult) -> str:
    if result.content.startswith("<tool_result"):
        return result.content
    return _wrap_tool_result(result.requested_mode, result.content)


def _tool_result_preview(content: str) -> str:
    mode = _safe_tool_mode(_extract_tool_mode(content)) or "unknown"
    return json.dumps({"status": "received", "mode": mode})


def _extract_tool_mode(content: str) -> str | None:
    tool_match = _CONTROL_TOOL_RE.match(content.strip())
    if tool_match:
        return tool_match.group(1)
    tool_result_match = re.search(r'mode="([a-z_]+)"', content)
    if tool_result_match:
        return tool_result_match.group(1)
    return None


def _safe_tool_mode(mode: str | None) -> TutorMode | None:
    if mode in _VALID_MODES:
        return mode  # type: ignore[return-value]
    return None
