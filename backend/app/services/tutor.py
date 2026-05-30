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
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.prompts import prompt_registry
from backend.app.agents.provider_tools import (
    NormalizedToolCall,
    NormalizedToolResult,
    ProviderToolDefinition,
    normalize_tool_call,
)
from backend.app.agents.retrieval_tools import select_retrieval_tools
from backend.app.schemas.tutor import ConversationMessage, TutorMode
from backend.app.services.conversation_summaries import (
    LLMConversationSummarizer,
    maybe_generate_conversation_summary,
)
from backend.app.services.conversations import (
    TutorContext,
    TutorSourceMetadata,
    _run_retrieval_loop,
    build_tutor_context,
    get_next_turn_index,
    get_or_create_conversation,
    persist_assistant_turn,
    persist_tool_turn,
    persist_user_turn,
    prepare_regenerated_user_turn,
    replace_latest_user_turn,
    validate_concept_scope,
)
from backend.app.services.mastery import mark_learning_from_tutor_turn
from backend.app.services.quiz_guard import detect_quiz_answer_seeking
from backend.app.settings import settings

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

_STUCK_KEYWORDS: frozenset[str] = frozenset(
    {
        "i don't know",
        "i dont know",
        "i do not know",
        "don't know",
        "dont know",
        "do not know",
        "no idea",
        "not sure",
        "i'm stuck",
        "im stuck",
        "i am stuck",
        "i'm lost",
        "im lost",
        "i am lost",
        "lost",
        "i give up",
        "give up",
        "no clue",
        "can't figure",
        "cant figure",
        "i'm not sure",
    }
)

_VALID_MODES: frozenset[str] = frozenset(
    {"socratic", "direct", "repair", "quiz_prompt", "explore", "free_explore"}
)


def _infer_mode_from_message(message: str) -> TutorMode:
    """Heuristic tutor-mode inference from the learner's latest message.

    Single source of truth for keyword-based routing. Used both by the
    deterministic ``FallbackTutorModeClassifier`` and as the safety net when the
    LLM classifier emits prose instead of a control line. Order matters: explicit
    signals win over the socratic default. "I don't know" / "I'm stuck" routes to
    ``repair`` (teach) rather than ``socratic`` (ask yet another question).
    """
    text = message.lower()
    if any(keyword in text for keyword in _QUIZ_KEYWORDS):
        return "quiz_prompt"
    if any(keyword in text for keyword in _STUCK_KEYWORDS):
        return "repair"
    if any(keyword in text for keyword in _REPAIR_KEYWORDS):
        return "repair"
    if any(keyword in text for keyword in _EXPLORE_KEYWORDS):
        return "explore"
    if any(keyword in text for keyword in _DIRECT_KEYWORDS):
        return "direct"
    return "socratic"


_VALID_STATUSES: frozenset[str] = frozenset(
    {
        "selecting_mode",
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
_FINAL_MODE_TASKS: dict[str, str] = {
    "socratic": "tutor_socratic",
    "direct": "tutor_direct",
    "repair": "tutor_repair",
    "explore": "tutor_explore",
}
_FINAL_MODE_FALLBACKS: dict[str, str] = {
    "quiz_prompt": (
        "Briefly acknowledge that the learner seems ready for a level-up check. "
        "Direct them to use the quiz panel. Do not mark mastery directly. Keep it brief."
    ),
    "free_explore": (
        "Explore the learner's curiosity broadly but coherently. Stay educational, connect back "
        "to the current concept, and end with one reflection question. Default to a concise reply; "
        "use markdown headers/sub-structure only when they genuinely clarify a richer answer, and "
        "go longer only when the topic needs it. Do not flood the chat with walls of text."
    ),
}
_RETRIEVAL_PLANNING_MARKER = "## Retrieval tool planning only"
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
_CONTROL_TOOL_RE = re.compile(r'^<tool\s+name="get_tutor_instructions"\s+mode="([a-z_]+)"\s*/?>$')
# Unanchored twins: locate a control tag anywhere in the buffered classifier output
# (e.g. after a leading blank line) so a valid tag is still honoured.
_CONTROL_MODE_SEARCH_RE = re.compile(r'<mode\s+name="([a-z_]+)"\s*/?>')
_CONTROL_TOOL_SEARCH_RE = re.compile(
    r'<tool\s+name="get_tutor_instructions"\s+mode="([a-z_]+)"\s*/?>'
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
class _ModePreparation:
    """Result of the first-pass LLM call (mode selection).

    buffered_events — events to re-emit immediately (status, tool_call, tool_result, mode).
    messages_after_mode — message history to pass to the second LLM call (with retrieval
                          context optionally injected between prepare_mode and stream_text).
    """

    mode: TutorMode
    messages_after_mode: list[dict]
    buffered_events: tuple[TutorStreamChunk, ...]


@dataclass(frozen=True)
class _TurnDecision:
    """Unified classifier result: the answering mode plus the assessment-integrity flag.

    A single structured-JSON classifier call replaces the old tagged mode classifier
    AND the separate quiz-answer guard call.
    """

    mode: TutorMode
    blocks_quiz_answer: bool


class _ControlPrefixStripper:
    """Strip a leaked leading control tag even when it arrives across chunks."""

    def __init__(self) -> None:
        self._buffer = ""
        self._decided = False

    def feed(self, chunk: str) -> str:
        if self._decided:
            return chunk
        self._buffer += chunk
        stripped = _strip_control_prefix(self._buffer)
        if stripped != self._buffer:
            self._buffer = ""
            self._decided = True
            return stripped
        if self._could_be_control_prefix(self._buffer):
            return ""
        self._buffer = ""
        self._decided = True
        return stripped

    @staticmethod
    def _could_be_control_prefix(text: str) -> bool:
        stripped = text.lstrip()
        if not stripped:
            return True
        controls = (
            '<mode name="socratic" />',
            '<mode name="repair" />',
            '<mode name="quiz_prompt" />',
            '<mode name="explore" />',
            '<tool name="get_tutor_instructions" mode="direct" />',
            '<tool name="get_tutor_instructions" mode="free_explore" />',
        )
        return any(control.startswith(stripped) for control in controls)


@runtime_checkable
class TutorAgent(Protocol):
    def respond_stream(self, context: TutorContext) -> AsyncIterator[TutorStreamChunk]:
        """Yield a mixed stream of mode, reasoning, token, and tool events."""
        ...


class FallbackTutorModeClassifier:
    """Compatibility helper for tests and local deterministic mode checks."""

    async def classify(self, context: TutorContext) -> TutorMode:
        return _infer_mode_from_message(context.learner_message)


class LLMTutorAgent:
    """LLM-backed tutor agent with service-level tool continuation."""

    def __init__(
        self,
        client: LLMClient,
        registry: PromptRegistry = prompt_registry,
        max_tokens: int = 1024,
        mode_selection_thinking: bool | None = None,
    ) -> None:
        self._client = client
        self._registry = registry
        self._max_tokens = max(256, max_tokens)
        # The first (mode-selection) call is a pure classifier: it emits one control
        # line and stops, so it gets a small dedicated cap and never spends the full
        # answer budget on text that the second call regenerates anyway.
        self._mode_selection_max_tokens = max(16, settings.tutor_mode_selection_max_tokens)
        # The unified structured-JSON classifier needs a little more room than the
        # tagged classifier because it returns a small JSON object, not one tag.
        self._classifier_max_tokens = max(120, self._mode_selection_max_tokens * 3)
        # Whether the first (mode-selection) LLM call requests provider reasoning.
        # Off by default; surfacing raw mode-selection reasoning duplicates the
        # visible-answer thinking in the trace. Configurable via settings.
        self._mode_selection_thinking = (
            settings.tutor_mode_selection_thinking
            if mode_selection_thinking is None
            else mode_selection_thinking
        )

    @property
    def llm_client(self) -> LLMClient:
        """Expose the underlying LLM client for tool-loop callers."""
        return self._client

    async def respond_stream(self, context: TutorContext) -> AsyncIterator[TutorStreamChunk]:
        """Backward-compatible single-turn stream: prepare_mode → buffered events → stream_text."""
        prep = await self.prepare_mode(context)
        for event in prep.buffered_events:
            yield event
        async for event in self.stream_text(context, prep):
            yield event

    async def classify_turn(self, context: TutorContext) -> _TurnDecision:
        """Single enforced-JSON classifier call: pick the mode AND flag quiz-answer extraction.

        This replaces both the tagged mode classifier and the separate quiz-answer
        guard call. Structured output (``response_format=json_object`` on supported
        providers, plus a JSON-only prompt) prevents the model from accidentally
        answering the learner's question in the classifier completion. Reasoning is
        disabled so the confidential active quiz questions never surface as a trace.
        """
        system_prompt = self._registry.render(
            "tutor_turn_classifier", _context_to_classifier_vars(context)
        )
        messages = _build_chat_messages(
            system_prompt,
            context.recent_turns,
            context.learner_message,
        )
        raw = await self._client.chat(
            messages,
            temperature=0.0,
            max_tokens=self._classifier_max_tokens,
            response_format={"type": "json_object"},
            thinking=False,
        )
        return _parse_turn_decision(raw, context)

    def build_prep(self, mode: str, context: TutorContext) -> _ModePreparation:
        """Build the second-pass preparation for an already-decided mode.

        Used after ``classify_turn`` so mode resolution does not need a tagged
        first-pass stream. The base system prompt is a placeholder; ``_make_mode_prep``
        replaces it with the mode-specific final-response prompt.
        """
        messages = _build_chat_messages("", context.recent_turns, context.learner_message)
        return self._make_mode_prep(mode, context, messages, [])

    async def prepare_mode(self, context: TutorContext) -> _ModePreparation:
        """Run the first LLM call (mode selection only) and return a preparation object.

        The caller may inject retrieval context into prep.messages_after_mode between
        prepare_mode() and stream_text() to ground the final response in sources.
        """
        prompt_vars = _context_to_base_prompt_vars(context)
        system_prompt = self._registry.render("tutor_base", prompt_vars)
        messages = _build_chat_messages(
            system_prompt,
            context.recent_turns,
            context.learner_message,
        )
        return await self._run_first_pass(messages, context, thinking=self._mode_selection_thinking)

    async def prepare_mode_stream(self, context: TutorContext) -> AsyncIterator[tuple[str, object]]:
        """Streaming variant of prepare_mode.

        Yields live ``("status"|"thinking", chunk)`` events from the first LLM call as
        they arrive, then yields a final ``("__prep__", _ModePreparation)`` sentinel.
        This lets the caller stream first-call reasoning instead of buffering it until
        the first LLM call completes.
        """
        prompt_vars = _context_to_base_prompt_vars(context)
        system_prompt = self._registry.render("tutor_base", prompt_vars)
        messages = _build_chat_messages(
            system_prompt,
            context.recent_turns,
            context.learner_message,
        )
        async for item in self._run_first_pass_stream(
            messages, context, thinking=self._mode_selection_thinking
        ):
            yield item

    async def _run_first_pass_stream(
        self,
        messages: list[dict],
        context: TutorContext,
        *,
        thinking: bool | None = None,
    ) -> AsyncIterator[tuple[str, object]]:
        """Generator twin of _run_first_pass that streams pre-mode events live.

        Yields ``("status", ...)`` / ``("thinking", chunk)`` as the first LLM call emits
        them and a terminal ``("__prep__", _ModePreparation)``. Because reasoning is
        streamed here, the resulting prep carries no buffered pre-events (only the
        tool/mode events the caller still emits after mode resolution).
        """
        raw_stream = self._client_chat_stream_tagged(
            messages,
            temperature=0.0,
            max_tokens=self._mode_selection_max_tokens,
            thinking=thinking,
        )
        buffered_text = ""
        emitted_thinking_status = False
        saw_thinking = False

        async for kind, chunk in raw_stream:
            if kind == "thinking":
                if thinking is False:
                    continue
                if not emitted_thinking_status:
                    yield ("status", "thinking")
                    emitted_thinking_status = True
                saw_thinking = True
                yield ("thinking", chunk)
                continue

            buffered_text += chunk
            parsed = _parse_control_from_buffer(buffered_text)
            if parsed is None:
                continue

            mode = _resolve_control_mode(parsed, context)
            yield ("__prep__", self._make_mode_prep(mode, context, messages, []))
            return

        parsed = _parse_control_eof(buffered_text)
        if parsed is not None:
            mode = _control_value_to_mode(parsed)
            if mode is not None:
                yield ("__prep__", self._make_mode_prep(mode, context, messages, []))
                return

        if saw_thinking and not buffered_text.strip():
            yield ("status", "retrying_without_thinking")
            async for item in self._run_first_pass_stream(messages, context, thinking=False):
                yield item
            return

        # No control tag was produced: infer a sensible mode from the learner
        # message rather than blindly defaulting to socratic.
        yield (
            "__prep__",
            self._make_mode_prep(
                _infer_mode_from_message(context.learner_message), context, messages, []
            ),
        )

    async def _run_first_pass(
        self,
        messages: list[dict],
        context: TutorContext,
        *,
        thinking: bool | None = None,
        _pre_events: tuple[TutorStreamChunk, ...] = (),
    ) -> _ModePreparation:
        """Drive the first LLM call, stopping at the mode/tool control line.

        On a thinking-only response (reasoning but no text), retries without thinking
        enabled, accumulating pre-events across the recursion.
        """
        raw_stream = self._client_chat_stream_tagged(
            messages,
            temperature=0.0,
            max_tokens=self._mode_selection_max_tokens,
            thinking=thinking,
        )
        buffered_text = ""
        pre_events: list[TutorStreamChunk] = list(_pre_events)
        emitted_thinking_status = False
        saw_thinking = False

        async for kind, chunk in raw_stream:
            if kind == "thinking":
                if thinking is False:
                    continue
                if not emitted_thinking_status:
                    pre_events.append(("status", "thinking"))
                    emitted_thinking_status = True
                saw_thinking = True
                pre_events.append(("thinking", chunk))
                continue

            buffered_text += chunk
            parsed = _parse_control_from_buffer(buffered_text)
            if parsed is None:
                continue

            mode = _resolve_control_mode(parsed, context)
            # Control line (or prose fallback) resolved — stop reading the stream.
            return self._make_mode_prep(mode, context, messages, pre_events)

        # EOF path
        parsed = _parse_control_eof(buffered_text)
        if parsed is not None:
            mode = _control_value_to_mode(parsed)
            if mode is not None:
                return self._make_mode_prep(mode, context, messages, pre_events)

        # Thinking-only retry: model produced reasoning but no text/control line
        if saw_thinking and not buffered_text.strip():
            pre_events.append(("status", "retrying_without_thinking"))
            return await self._run_first_pass(
                messages,
                context,
                thinking=False,
                _pre_events=tuple(pre_events),
            )

        # No control tag was produced (the classifier wrote prose or nothing):
        # infer a mode from the learner message instead of blindly choosing
        # socratic, so "I don't know" turns into teaching rather than a question.
        return self._make_mode_prep(
            _infer_mode_from_message(context.learner_message), context, messages, pre_events
        )

    def _make_mode_prep(
        self,
        mode: str,
        context: TutorContext,
        messages: list[dict],
        pre_events: list[TutorStreamChunk],
    ) -> _ModePreparation:
        """Build a _ModePreparation given a resolved mode.

        For tool-gated modes: calls _get_tutor_instructions to resolve the instruction
        content, builds the tool-call / tool-result message history, and replays the
        gated-mode instructions for the second call.

        For non-tool modes: appends a synthetic mode-hint assistant message so the
        second LLM call does not re-emit the control header.
        """
        if mode in _TOOL_GATED_MODES:
            tool_result = self._get_tutor_instructions(mode, context)
            if context.mastery_status == "mastered" and tool_result.final_mode == "direct":
                tool_result = _without_instruction_tool_replay(tool_result)
            tool_call_content = _tool_call_content(tool_result.requested_mode)
            tool_message = _tool_result_content(tool_result)
            tool_events: tuple[TutorStreamChunk, ...]
            if tool_result.normalized_call is None and tool_result.normalized_result is None:
                tool_events = ()
            else:
                tool_events = (
                    ("status", "calling_tool"),
                    ("tool_call", tool_call_content),
                    ("status", "tool_called"),
                    ("tool_result", tool_message),
                    ("status", "tool_complete"),
                )
            buffered_events: tuple[TutorStreamChunk, ...] = (
                tuple(pre_events) + tool_events + (("mode", tool_result.final_mode),)
            )
            messages_after_mode = _replace_system_prompt(
                _append_instruction_tool_replay(
                    messages,
                    tool_call_content,
                    tool_message,
                    tool_result,
                ),
                self._final_response_prompt(tool_result.final_mode, context),
            )
            return _ModePreparation(
                mode=tool_result.final_mode,
                messages_after_mode=messages_after_mode,
                buffered_events=buffered_events,
            )
        else:
            buffered_events = tuple(pre_events) + (("mode", mode),)  # type: ignore[assignment]
            messages_after_mode = _replace_system_prompt(
                messages,
                self._final_response_prompt(mode, context),
            )
            return _ModePreparation(
                mode=mode,  # type: ignore[arg-type]
                messages_after_mode=messages_after_mode,
                buffered_events=buffered_events,
            )

    async def stream_text(
        self,
        context: TutorContext,
        prep: _ModePreparation,
        *,
        messages: list[dict] | None = None,
    ) -> AsyncIterator[TutorStreamChunk]:
        """Run the second LLM call and stream the final visible text.

        *messages* overrides prep.messages_after_mode when the caller has injected
        retrieval context between prepare_mode and stream_text.
        """
        effective_messages = messages if messages is not None else prep.messages_after_mode
        effective_messages = _strip_control_assistant_seeds(effective_messages)

        emitted_thinking_status = False
        async for kind, chunk in self._chat_stream_with_empty_retry(
            effective_messages,
            temperature=0.4,
            max_tokens=self._max_tokens,
        ):
            if kind == "status":
                yield ("status", chunk)
            elif kind == "thinking":
                if not emitted_thinking_status:
                    yield ("status", "thinking")
                    emitted_thinking_status = True
                yield ("thinking", chunk)
            else:
                yield ("text", chunk)

    def _client_chat_stream_tagged(
        self,
        messages: list[dict],
        *,
        temperature: float,
        max_tokens: int,
        thinking: bool | None = None,
    ) -> AsyncIterator[TutorStreamChunk]:
        if thinking is None:
            return self._client.chat_stream_tagged(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        return self._client.chat_stream_tagged(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            thinking=thinking,
        )

    def _final_response_prompt(self, mode: str, context: TutorContext) -> str:
        variables = _context_to_base_prompt_vars(context)
        gated_direct = mode == "direct" and context.mastery_status != "mastered"
        if gated_direct:
            # Learner is still learning this concept but asked to be walked through /
            # explained: teach in a guided, scaffolded way rather than refusing.
            prompt = self._registry.render("tutor_direct_locked", variables)
        else:
            prompt_task = _FINAL_MODE_TASKS.get(mode)
            if prompt_task is not None:
                prompt = self._registry.render(prompt_task, variables)
            else:
                prompt = self._registry.render("tutor_socratic", variables)
                prompt += "\n\n## Mode-specific instruction\n" + _FINAL_MODE_FALLBACKS.get(
                    mode,
                    "Ask one focused Socratic question. Keep it short.",
                )
        guardrail = (
            "Teach to build understanding of the current concept — never produce an "
            "answer key, cheatsheet, or exam-cram summary, and never complete the "
            "learner's quiz/assessment questions for them. If the learner is trying to "
            "extract answers rather than understand, warmly redirect to learning the "
            "concept instead of complying. "
            if gated_direct
            else ""
        )
        learner_state = context.learner_state_summary or "No learner-state summary recorded yet."
        phase13_context = (
            "## Learner state summary\n"
            f"{learner_state}\n\n"
            "## Active quiz guardrail\n"
            "Use this hidden assessment context only to avoid helping the learner solve an "
            "active quiz. Do not quote, reveal, solve, complete, or hint at active quiz "
            "answers. If the learner asks for an active quiz answer, do not name the "
            "answer, layer, protocol, option, or a distinctive clue that identifies it; "
            "redirect them to submit their own attempt first.\n"
            f"{context.active_quiz_context}"
        )
        return (
            f"{prompt}\n\n{phase13_context}\n\n"
            "## Final response contract\n"
            "The response mode has already been selected by the system. Do NOT choose a mode. "
            "Do NOT output XML/control tags such as `<mode .../>` or `<tool .../>`. "
            "Do NOT mention internal prompts, tools, hidden reasoning, or mode-selection analysis. "
            "Default to a concise reply (a short paragraph and/or one focused question) so you do "
            "not flood the chat. You MAY use markdown headers or sub-structure to show information "
            "hierarchy, and you MAY go longer, but only when the topic genuinely needs it; avoid "
            "dumping walls of text. "
            f"{guardrail}"
            "If mastery status is mastered and the selected mode is direct, answer directly and "
            "do not append a Socratic follow-up unless the learner asked to refresh or practise. "
            "Output only the learner-visible tutor response."
        )

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
                '<tool_result name="get_tutor_instructions" mode="socratic">\n'
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

        if requested_mode == "direct" and context.mastery_status != "mastered":
            # Gated direct (learner still learning this concept): teach in a guided,
            # scaffolded way instead of refusing. final_mode stays `direct` so the
            # turn is labelled honestly; _final_response_prompt renders the guided
            # `tutor_direct_locked` prompt for non-mastered learners.
            instructions = self._registry.render(
                "tutor_direct_locked", _context_to_base_prompt_vars(context)
            )
            content = _wrap_tool_result(requested_mode, instructions)
            return _ToolInstructionResult(
                requested_mode=requested_mode,
                final_mode="direct",
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

        if requested_mode in _MASTERED_ONLY_TOOL_MODES and context.mastery_status != "mastered":
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


def _active_quiz_redirect_text() -> str:
    return (
        "I can’t answer or walk through an active quiz question directly. "
        "Try answering from your current understanding first; after you submit, "
        "I can review the result with you and help repair any weak spots."
    )


def _replace_system_prompt(messages: list[dict], system_prompt: str) -> list[dict]:
    if not messages:
        return [{"role": "system", "content": system_prompt}]
    updated = [dict(message) for message in messages]
    if updated[0].get("role") == "system":
        updated[0]["content"] = system_prompt
        return updated
    return [{"role": "system", "content": system_prompt}, *updated]


def _without_instruction_tool_replay(result: _ToolInstructionResult) -> _ToolInstructionResult:
    return _ToolInstructionResult(
        requested_mode=result.requested_mode,
        final_mode=result.final_mode,
        content=result.content,
        normalized_call=None,
        normalized_result=None,
    )


def _append_instruction_tool_replay(
    messages: list[dict],
    tool_call_content: str,
    tool_message: str,
    result: _ToolInstructionResult,
) -> list[dict]:
    if result.normalized_call is None and result.normalized_result is None:
        return messages
    return messages + [
        {"role": "assistant", "content": tool_call_content},
        {"role": "assistant", "content": tool_message},
    ]


def _strip_control_assistant_seeds(messages: list[dict]) -> list[dict]:
    return [
        message
        for message in messages
        if not (
            message.get("role") == "assistant"
            and _parse_control_eof(str(message.get("content", ""))) is not None
        )
    ]


def _sanitize_stream_event(
    kind: str,
    chunk: str,
    control_prefix_stripper: _ControlPrefixStripper,
) -> TutorStreamChunk:
    if kind != "text":
        return kind, chunk
    return kind, control_prefix_stripper.feed(chunk)


def _retrieval_planning_messages(messages: list[dict]) -> list[dict]:
    instruction = (
        f"{_RETRIEVAL_PLANNING_MARKER}\n"
        "You are selecting retrieval tools for the next tutor response. "
        "If source content is needed, call the available retrieval tools. "
        "If no source content is needed, return no tool calls and answer the learner directly "
        "in the already-selected mode. "
        "Do not choose a tutor mode. Do not output `<mode .../>` tags. "
        "The prompt already lists the current concept, graph neighbours, and linked source titles; "
        "do not search merely to add background. Use tools only when the next response would "
        "be materially better grounded by specific source content. Prefer search_sources when "
        "the learner asks about source content, and call read_document_section only if the "
        "search snippet is not enough. Once you have enough context for the next answer, "
        "stop calling tools. "
        "For get_concept_sources and get_graph_neighbourhood, omit concept_id unless you are given "
        "an explicit UUID; the backend will use the current concept."
    )
    return [
        (
            {"role": "system", "content": f"{message.get('content', '')}\n\n{instruction}"}
            if index == 0 and message.get("role") == "system"
            else dict(message)
        )
        for index, message in enumerate(messages)
    ]


def _restore_final_system_prompt(
    final_messages: list[dict],
    retrieval_messages: list[dict],
) -> list[dict]:
    if not final_messages:
        return retrieval_messages
    restored = [dict(message) for message in retrieval_messages]
    final_system = final_messages[0] if final_messages[0].get("role") == "system" else None
    if final_system is None:
        return restored
    if restored and restored[0].get("role") == "system":
        restored[0] = dict(final_system)
        return restored
    return [dict(final_system), *restored]


def _should_replay_retrieval_result(result: NormalizedToolResult) -> bool:
    return (
        result.name == "read_document_section"
        and not result.is_error
        and bool(result.content.strip())
    )


async def stream_chat_response(
    session: AsyncSession,
    agent: TutorAgent,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    message: str,
    conversation_id: uuid.UUID | None,
    regenerate: bool = False,
    replace_latest_user: bool = False,
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

    message = message.strip()
    if regenerate and replace_latest_user:
        yield _sse(
            "error",
            {
                "type": "error",
                "code": "invalid_request",
                "message": "regenerate and replace_latest_user cannot both be true",
            },
        )
        return

    if regenerate:
        try:
            user_turn = await prepare_regenerated_user_turn(session, conversation.id, message)
        except LookupError as exc:
            yield _sse("error", {"type": "error", "code": "not_found", "message": str(exc)})
            return
        except ValueError as exc:
            yield _sse(
                "error",
                {"type": "error", "code": "invalid_regenerate", "message": str(exc)},
            )
            return
        user_turn_index = user_turn.turn_index
    elif replace_latest_user:
        try:
            user_turn = await replace_latest_user_turn(session, conversation.id, message)
        except LookupError as exc:
            yield _sse("error", {"type": "error", "code": "not_found", "message": str(exc)})
            return
        user_turn_index = user_turn.turn_index
    else:
        user_turn_index = await get_next_turn_index(session, conversation.id)
        await persist_user_turn(session, conversation.id, message, user_turn_index)

    context = await build_tutor_context(
        session,
        conversation=conversation,
        concept=concept,
        trail=trail,
        learner_message=message,
        user_turn_index=user_turn_index,
    )

    async def _emit_quiz_redirect() -> AsyncIterator[str]:
        """Deterministically refuse to answer an active quiz question."""
        redirect_mode: TutorMode = "direct"
        redirect_text = _active_quiz_redirect_text()
        yield _sse("mode", {"type": "mode", "mode": redirect_mode})
        yield _sse("status", {"type": "status", "status": "responding"})
        yield _sse("token", {"type": "token", "content": redirect_text})
        redirect_turn = await persist_assistant_turn(
            session,
            conversation.id,
            redirect_text,
            redirect_mode,
            user_turn_index + 1,
            reasoning=None,
            reasoning_parts=None,
        )
        redirect_schema = ConversationMessage.model_validate(redirect_turn)
        yield _sse(
            "done",
            {
                "type": "done",
                "conversation_id": str(conversation.id),
                "message": redirect_schema.model_dump(mode="json"),
                "mastery_update": {
                    "concept_id": str(mastery_state.concept_id),
                    "status": mastery_state.status,
                    "score": mastery_state.score,
                },
            },
        )

    # Free, deterministic short-circuit: verbatim copy of an active quiz question.
    if context.active_quiz_question_match:
        async for event in _emit_quiz_redirect():
            yield event
        return

    # Legacy semantic guard, only for agents WITHOUT the unified classifier.
    # Agents with `classify_turn` fold this decision into the single classifier call.
    if context.active_quiz_prompts and not hasattr(agent, "classify_turn"):
        guard_client = getattr(agent, "llm_client", None)
        if guard_client is not None and hasattr(guard_client, "chat"):
            try:
                blocked = await detect_quiz_answer_seeking(
                    guard_client,
                    learner_message=message,
                    quiz_prompts=context.active_quiz_prompts,
                )
            except Exception as exc:
                logger.warning("Quiz answer guard failed: %s", exc)
                blocked = False
            if blocked:
                async for event in _emit_quiz_redirect():
                    yield event
                return

    mode: TutorMode | None = None
    full_text = ""
    full_reasoning = ""
    reasoning_parts: list[dict] = []
    tool_turns: list[tuple[str, str, str, str | None]] = []
    retrieval_tool_turns: list[tuple[str, str, str, str | None]] = []
    emitted_response_status = False
    control_prefix_stripper = _ControlPrefixStripper()

    def _process_event(kind: str, chunk: str) -> None:
        """Apply a (kind, chunk) event to mutable accumulators (no SSE yield here)."""
        nonlocal mode, full_text, full_reasoning, emitted_response_status
        if kind == "mode":
            parsed_mode = chunk if chunk in _VALID_MODES else "socratic"
            mode = parsed_mode  # type: ignore[assignment]
        elif kind == "thinking":
            full_reasoning += chunk
            if reasoning_parts and reasoning_parts[-1].get("kind") == "thinking":
                reasoning_parts[-1]["text"] = f"{reasoning_parts[-1].get('text', '')}{chunk}"
            else:
                reasoning_parts.append({"kind": "thinking", "text": chunk})
        elif kind == "tool_call":
            tool_call_nc = _normalize_tutor_instruction_content(chunk)
            tool_mode = _safe_tool_mode(
                str(tool_call_nc.arguments.get("mode")) if tool_call_nc.is_valid else None
            )
            tool_turns.append(("assistant", "tool_call", chunk, tool_mode))
            reasoning_parts.append(
                {"kind": "tool_call", "name": "get_tutor_instructions", "mode": tool_mode}
            )
        elif kind == "tool_result":
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
        elif kind == "status":
            if chunk == "responding":
                emitted_response_status = True
            status = chunk if chunk in _VALID_STATUSES else "thinking"
            if status != "responding":
                reasoning_parts.append({"kind": "status", "status": status})
        else:
            full_text += chunk

    async def _emit_event(kind: str, chunk: str):
        """Yield the SSE wire encoding for a (kind, chunk) event."""
        nonlocal emitted_response_status
        if kind == "status":
            status = chunk if chunk in _VALID_STATUSES else "thinking"
            yield _sse("status", {"type": "status", "status": status})
        elif kind == "tool_call":
            tool_call_nc = _normalize_tutor_instruction_content(chunk)
            tool_mode = _safe_tool_mode(
                str(tool_call_nc.arguments.get("mode")) if tool_call_nc.is_valid else None
            )
            yield _sse(
                "tool_call",
                {"type": "tool_call", "name": "get_tutor_instructions", "mode": tool_mode},
            )
        elif kind == "tool_result":
            tool_mode = _safe_tool_mode(_extract_tool_mode(chunk))
            preview = _tool_result_preview(chunk)
            yield _sse(
                "tool_result",
                {
                    "type": "tool_result",
                    "name": "get_tutor_instructions",
                    "mode": tool_mode,
                    "result": preview,
                },
            )
        elif kind == "mode":
            parsed_mode = chunk if chunk in _VALID_MODES else "socratic"
            yield _sse("mode", {"type": "mode", "mode": parsed_mode})
        elif kind == "thinking":
            yield _sse("thinking", {"type": "thinking", "content": chunk})
        else:
            visible_chunk = chunk
            if not emitted_response_status:
                yield _sse("status", {"type": "status", "status": "responding"})
                emitted_response_status = True
            if visible_chunk:
                yield _sse("token", {"type": "token", "content": visible_chunk})

    try:
        if hasattr(agent, "stream_text") and (
            hasattr(agent, "classify_turn") or hasattr(agent, "prepare_mode")
        ):
            # ---------------------------------------------------------------
            # Two-phase path: mode selection → retrieval → text generation
            # ---------------------------------------------------------------

            # Phase 1: mode selection.
            # Announce that we're choosing an answering mode before the first LLM
            # call. The mode-selection call no longer streams raw reasoning by
            # default (see Settings.tutor_mode_selection_thinking), so this status
            # plus the post-mode `mode` event is the learner-visible first-phase
            # trace: "choosing answering mode → <mode>".
            _process_event("status", "selecting_mode")
            async for sse in _emit_event("status", "selecting_mode"):
                yield sse

            prep: _ModePreparation | None = None
            if hasattr(agent, "classify_turn") and hasattr(agent, "build_prep"):
                # Unified, enforced-JSON classifier: one call decides the mode AND
                # whether the learner is extracting an active quiz answer.
                decision = await agent.classify_turn(context)  # type: ignore[union-attr]
                if decision.blocks_quiz_answer and context.active_quiz_prompts:
                    async for event in _emit_quiz_redirect():
                        yield event
                    return
                prep = agent.build_prep(decision.mode, context)  # type: ignore[union-attr]
            else:
                # Legacy tagged classifier path. When the agent supports
                # prepare_mode_stream, first-call reasoning is streamed live.
                if hasattr(agent, "prepare_mode_stream"):
                    async for kind, payload in agent.prepare_mode_stream(context):  # type: ignore[union-attr]
                        if kind == "__prep__":
                            prep = cast(_ModePreparation, payload)
                            break
                        kind, chunk = _sanitize_stream_event(
                            kind, str(payload), control_prefix_stripper
                        )
                        _process_event(kind, chunk)
                        async for sse in _emit_event(kind, chunk):
                            yield sse
                if prep is None:
                    prep = await agent.prepare_mode(context)  # type: ignore[union-attr]
            if prep is None:
                raise RuntimeError("Tutor mode preparation failed")

            # Emit buffered events from phase 1 (status, tool_call, tool_result, mode)
            for kind, chunk in prep.buffered_events:
                kind, chunk = _sanitize_stream_event(kind, chunk, control_prefix_stripper)
                _process_event(kind, chunk)
                async for sse in _emit_event(kind, chunk):
                    yield sse

            # Retrieval loop — between phases so the LLM sees retrieved content.
            # The loop runs when there is a usable LLM client AND the concept has
            # either linked sources or a cached primer. On source-less concepts the
            # primer tool is still worth offering so the tutor can re-orient a
            # learner on later turns. The opening-turn primer auto-injection
            # (build_tutor_context) is unchanged; on later turns the primer only
            # reaches the model through get_concept_primer.
            llm_client_for_retrieval = getattr(agent, "llm_client", None)
            enriched_messages = prep.messages_after_mode
            # Local import mirrors build_tutor_context and avoids a circular import.
            from backend.app.services.concept_primers import read_cached_primer

            has_sources = len(context.sources) > 0
            primer_available = read_cached_primer(concept) is not None
            offered_tools = select_retrieval_tools(
                has_sources=has_sources,
                has_primer=primer_available,
            )
            if llm_client_for_retrieval is not None and (has_sources or primer_available):
                try:
                    retrieval_messages = _retrieval_planning_messages(prep.messages_after_mode)
                    retrieval_loop = await _run_retrieval_loop(
                        retrieval_messages,
                        offered_tools,
                        session=session,
                        workspace_id=workspace_id,
                        concept_id=concept_id,
                        llm_client=llm_client_for_retrieval,
                    )
                    retrieval_results = retrieval_loop.tool_results
                    enriched_messages = _restore_final_system_prompt(
                        prep.messages_after_mode,
                        retrieval_loop.messages,
                    )
                except Exception as exc:
                    logger.warning("Retrieval loop failed: %s", exc)
                    retrieval_results = []
                    retrieval_loop = None
                    enriched_messages = prep.messages_after_mode

                for result in retrieval_results:
                    retrieval_tool_turns.append(
                        (
                            "assistant",
                            "tool_call",
                            json.dumps(
                                {
                                    "name": result.name,
                                    "call_id": result.call_id,
                                    "query": result.public_preview.get("query"),
                                }
                            ),
                            None,
                        )
                    )
                    reasoning_parts.append(
                        {
                            "kind": "tool_call",
                            "name": result.name,
                            "mode": None,
                            "query": result.public_preview.get("query"),
                        }
                    )
                    reasoning_parts.append(
                        {
                            "kind": "tool_result",
                            "name": result.name,
                            "mode": None,
                            "result": result.preview_json(),
                        }
                    )
                    if _should_replay_retrieval_result(result):
                        retrieval_tool_turns.append(("tool", "tool_result", result.content, None))
                    yield _sse(
                        "tool_call",
                        {
                            "type": "tool_call",
                            "name": result.name,
                            "query": result.public_preview.get("query"),
                        },
                    )
                    yield _sse(
                        "tool_result",
                        {
                            "type": "tool_result",
                            "name": result.name,
                            "result": result.preview_json(),
                        },
                    )

                if retrieval_loop is not None and not retrieval_results and retrieval_loop.thinking:
                    _process_event("thinking", retrieval_loop.thinking)
                    async for sse in _emit_event("thinking", retrieval_loop.thinking):
                        yield sse

                if (
                    retrieval_loop is not None
                    and not retrieval_results
                    and retrieval_loop.text.strip()
                ):
                    kind, chunk = _sanitize_stream_event(
                        "text",
                        retrieval_loop.text,
                        control_prefix_stripper,
                    )
                    _process_event(kind, chunk)
                    async for sse in _emit_event(kind, chunk):
                        yield sse
                    continue_final_generation = False
                else:
                    continue_final_generation = True
            else:
                continue_final_generation = True

            if continue_final_generation:
                # Phase 2: text generation with retrieval-enriched messages
                async for kind, chunk in agent.stream_text(  # type: ignore[union-attr]
                    context, prep, messages=enriched_messages
                ):
                    kind, chunk = _sanitize_stream_event(kind, chunk, control_prefix_stripper)
                    _process_event(kind, chunk)
                    async for sse in _emit_event(kind, chunk):
                        yield sse

        else:
            # ---------------------------------------------------------------
            # Backward-compatible path for agents without two-phase support
            # ---------------------------------------------------------------
            async for kind, chunk in agent.respond_stream(context):
                kind, chunk = _sanitize_stream_event(kind, chunk, control_prefix_stripper)
                _process_event(kind, chunk)
                async for sse in _emit_event(kind, chunk):
                    yield sse

    except Exception as exc:
        logger.error("Tutor agent failed: %s", exc)
        await session.rollback()
        yield _sse("error", {"type": "error", "code": "llm_error", "message": "Generation failed"})
        return

    if not full_text.strip():
        # Any completion with no visible tutor text is an error — whether or not the
        # model produced reasoning. Roll back so we never persist a blank assistant
        # bubble or emit a `done` for an empty answer.
        logger.warning("Tutor generation ended without a visible tutor response")
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
    for role, kind, content, tool_mode in tool_turns + retrieval_tool_turns:
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

    # Emit `done` before the conversation summary so the learner sees the finished
    # answer immediately; the summary is a background-style refinement that must
    # not add latency to the visible turn.
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

    summary_client = getattr(agent, "llm_client", None)
    if summary_client is not None and hasattr(summary_client, "chat"):
        try:
            await maybe_generate_conversation_summary(
                session,
                LLMConversationSummarizer(summary_client),
                conversation_id=conversation.id,
                through_turn_index=assistant_turn.turn_index,
                recent_visible_turns_limit=settings.tutor_recent_visible_turns_limit,
                history_char_budget=settings.tutor_history_char_budget,
                batch_size=settings.tutor_summary_batch_size,
            )
            await session.commit()
        except Exception as exc:
            logger.warning("Conversation summary generation failed: %s", exc)
            await session.rollback()


def _parse_control_from_buffer(buffer: str) -> _ParsedControl | None:
    # A valid control tag anywhere in the buffer wins, even if the model emitted
    # leading whitespace or a blank line before it.
    tool_match = _CONTROL_TOOL_SEARCH_RE.search(buffer)
    if tool_match:
        return _ParsedControl(kind="tool", value=tool_match.group(1), remainder="")

    mode_match = _CONTROL_MODE_SEARCH_RE.search(buffer)
    if mode_match:
        return _ParsedControl(kind="mode", value=mode_match.group(1), remainder="")

    newline = buffer.find("\n")
    if newline == -1:
        return None

    # The first complete line is prose and cannot still grow into a control tag:
    # the classifier ignored the contract and is writing a reply. Signal a
    # fallback so the caller infers a mode from the learner message instead of
    # blindly defaulting to socratic.
    first_line = buffer[:newline].strip()
    if first_line and not _ControlPrefixStripper._could_be_control_prefix(first_line):
        return _ParsedControl(kind="fallback", value="socratic", remainder=buffer)

    return None


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


def _resolve_control_mode(parsed: _ParsedControl, context: TutorContext) -> TutorMode:
    """Map a parsed control result to a concrete mode for the turn.

    A real ``<mode>``/``<tool>`` tag is authoritative. When the classifier emitted
    prose instead (``kind == "fallback"``), infer the mode from the learner's
    latest message so a "I don't know" turn becomes teaching (repair) rather than
    yet another Socratic question.
    """
    if parsed.kind == "fallback":
        return _infer_mode_from_message(context.learner_message)
    mode = _control_value_to_mode(parsed)
    return mode if mode is not None else "socratic"


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


def _format_primer(primer) -> str:
    """Render a cached concept primer as opening-turn context, or "" when absent.

    Only used opportunistically on the opening turn so the tutor's framing aligns
    with the concept glossary. Never triggers primer generation.
    """
    if primer is None:
        return ""
    key_terms = "\n".join(f"- {term.term}: {term.definition}" for term in primer.key_terms)
    return (
        "\n\n## Concept primer (align your framing and vocabulary with this)\n"
        f"Overview: {primer.overview}\n\n"
        f"Key terms:\n{key_terms}"
    )


def _render_opening_guidance(context: TutorContext) -> str:
    """Render the worked-example-first opening instructions for an opening turn.

    Returns "" on non-opening turns, leaving normal multi-mode behaviour untouched.
    The opening guidance text lives in the versioned ``tutor_opening`` prompt; a
    cached primer, when present, is folded in as additional framing context.
    """
    if not context.is_opening_turn:
        return ""
    return prompt_registry.render(
        "tutor_opening",
        {"primer_context": _format_primer(context.primer)},
    )


def _context_to_base_prompt_vars(context: TutorContext) -> dict[str, str]:
    recent_turns_text = (
        "\n".join(f"{turn.role.upper()}: {turn.content}" for turn in context.recent_turns) or "none"
    )
    summary_text = (
        context.conversation_summary.summary_text
        if context.conversation_summary is not None
        else ""
    )

    learner_state_text = context.learner_state_summary or "No learner-state summary recorded yet."

    return {
        "concept": f"{context.concept.title} ({context.concept.concept_level})",
        "concept_id": str(context.concept.id),
        "concept_level": context.concept.concept_level,
        "prerequisites": ", ".join(node.title for node in context.prerequisites) or "none",
        "contained_nodes": ", ".join(node.title for node in context.contained_nodes) or "none",
        "containing_nodes": ", ".join(node.title for node in context.containing_nodes) or "none",
        "application_nodes": ", ".join(node.title for node in context.application_nodes) or "none",
        "related_nodes": ", ".join(node.title for node in context.related) or "none",
        "mastery_status": context.mastery_status,
        "bloom_target": context.concept.bloom_level,
        "learning_goal": context.trail.goal,
        "learner_prior_knowledge": context.prior_knowledge or "none",
        "learner_state_summary": learner_state_text,
        "active_quiz_context": context.active_quiz_context,
        "sources": _format_sources(context.sources),
        "conversation_summary": summary_text,
        "recent_turns": recent_turns_text,
        "learner_message": context.learner_message,
        "opening_turn": "yes" if context.is_opening_turn else "no",
        "opening_guidance": _render_opening_guidance(context),
    }


def _context_to_classifier_vars(context: TutorContext) -> dict[str, str]:
    learner_state = context.learner_state_summary or "No learner-state summary recorded yet."
    summary = (
        context.conversation_summary.summary_text
        if context.conversation_summary is not None
        else ""
    )
    quiz_questions = (
        "\n".join(f"- {prompt}" for prompt in context.active_quiz_prompts)
        or "none (no active quiz)"
    )
    return {
        "concept": f"{context.concept.title} ({context.concept.concept_level})",
        "concept_level": context.concept.concept_level,
        "mastery_status": context.mastery_status,
        "learning_goal": context.trail.goal,
        "learner_prior_knowledge": context.prior_knowledge or "none",
        "learner_state_summary": learner_state,
        "conversation_summary": summary,
        "active_quiz_questions": quiz_questions,
        "learner_message": context.learner_message,
    }


def _parse_turn_decision(raw: str, context: TutorContext) -> _TurnDecision:
    """Parse the structured classifier output, with safe fallbacks.

    On any parse failure, fall back to keyword-based mode inference and do not
    block (exact-prompt matching still covers verbatim copies). ``blocks`` is only
    honoured when an active quiz draft actually exists.
    """
    mode: str = _infer_mode_from_message(context.learner_message)
    blocks = False
    data = _safe_load_json(raw)
    if isinstance(data, dict):
        raw_mode = data.get("mode")
        if isinstance(raw_mode, str) and raw_mode in _VALID_MODES:
            mode = raw_mode
        blocks = data.get("blocks_active_quiz_answer") is True
    if not context.active_quiz_prompts:
        blocks = False
    return _TurnDecision(mode=cast(TutorMode, mode), blocks_quiz_answer=blocks)


def _safe_load_json(raw: str) -> object:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        return None


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
