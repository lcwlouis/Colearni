"""Unified async LLM client with provider routing.

Supports:
  - OpenAI via the Responses API (``provider=openai``): uses ``client.responses.create``
    which surfaces reasoning summaries (``reasoning.summary='auto'``) when
    ``thinking_enabled=True``.  The Responses API is OpenAI's recommended path for
    all reasoning models (GPT-5, o-series, etc.).
  - OpenAI-compatible endpoints (OpenRouter, DeepSeek, Gemini, custom) via the
    openai SDK + ``base_url`` override: uses ``client.chat.completions.create``.
    DeepSeek-R1 exposes reasoning tokens in the non-standard ``reasoning_content``
    or ``reasoning`` delta field which _extract_delta_reasoning() handles.
  - Anthropic natively via the anthropic SDK (lazy import).

Adding a new provider:
  1. Add an entry to PROVIDER_BASE_URLS (if OpenAI-compatible Chat Completions), OR
  2. Add it to _RESPONSES_API_PROVIDERS if it uses the OpenAI Responses API, OR
  3. Add it to _NATIVE_SDK_PROVIDERS and add a branch in chat() / chat_stream_tagged().

Extended thinking / reasoning:
  Controlled by three settings on LLMClient (or via Settings):
    thinking_enabled  — master toggle; defaults to False.
    thinking_budget   — Anthropic: budget_tokens (min 1024).
    thinking_level    — reasoning effort: "low"|"medium"|"high".

  Provider behaviour:
    openai      — adds reasoning={effort, summary='auto'} to the Responses API request.
                  Raw reasoning tokens are never exposed by OpenAI; only a human-readable
                  summary is returned.  Summaries stream as reasoning_summary_text.delta.
    openrouter  — DeepSeek-R1 exposes raw reasoning in reasoning_content / reasoning delta.
    deepseek    — Same as openrouter via the native DeepSeek endpoint.
    anthropic   — Thinking blocks stream natively via the Anthropic SDK.

  When a model does not support thinking the client silently retries without
  thinking params so no calling code needs to handle model capability checks.

Usage:
    client = LLMClient.from_settings(settings)
    text = await client.chat([{"role": "user", "content": "Hello"}])
    async for chunk in client.chat_stream([{"role": "user", "content": "Hello"}]):
        print(chunk, end="", flush=True)
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Sequence

from backend.app.agents.provider_tools import (
    AnthropicStreamState,
    NormalizedStreamEvent,
    ProviderToolDefinition,
    anthropic_tool_definitions,
    normalize_anthropic_stream_event,
    normalize_openai_chat_stream_chunk,
    normalize_openai_chat_tool_call,
    normalize_openai_responses_stream_event,
    openai_chat_tool_definitions,
    openai_responses_tool_definitions,
)
from backend.app.settings import Settings

# Type alias for tagged token stream: (kind, chunk) where kind is "text" or "thinking".
TaggedChunk = tuple[str, str]

logger = logging.getLogger(__name__)

# OpenAI-compatible providers: base URL is all that differs.
# Empty string means "use SDK default" (i.e. api.openai.com).
PROVIDER_BASE_URLS: dict[str, str] = {
    "openai": "",
    "openrouter": "https://openrouter.ai/api/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
}

# Providers that use a non-OpenAI SDK
_NATIVE_SDK_PROVIDERS = {"anthropic"}

# Providers that use the OpenAI Responses API (client.responses.create) instead
# of Chat Completions (client.chat.completions.create).  The Responses API is
# OpenAI's recommended path for all reasoning models and is the only way to
# surface reasoning summaries from OpenAI models.
_RESPONSES_API_PROVIDERS = {"openai"}

SUPPORTED_PROVIDERS = sorted(PROVIDER_BASE_URLS) + sorted(_NATIVE_SDK_PROVIDERS)

# Keywords that indicate a thinking/reasoning parameter was rejected by the API.
# Used to detect when a model doesn't support thinking so we can retry without.
_THINKING_ERROR_KEYWORDS = frozenset(["reasoning_effort", "thinking", "budget_tokens"])

# Non-standard delta field names used by reasoning models across providers.
# Checked in order; the first non-empty value wins.
#   - "reasoning_content": Native DeepSeek API (plain string per delta)
#   - "reasoning":         Some providers (plain string per delta)
# OpenRouter uses a structured ``reasoning_details`` array instead —
# handled separately by _extract_delta_reasoning_details().
_REASONING_FIELDS = ("reasoning_content", "reasoning")


def _is_thinking_error(exc: Exception) -> bool:
    """Return True if the exception looks like a rejected thinking/reasoning param."""
    msg = str(exc).lower()
    return any(k in msg for k in _THINKING_ERROR_KEYWORDS)


def _extract_delta_reasoning_details(delta) -> str | None:
    """Extract reasoning text from the OpenRouter ``reasoning_details`` array.

    OpenRouter streaming delivers reasoning in ``choices[].delta.reasoning_details``
    as a list of typed objects.  Each object has a ``type`` (e.g.
    ``reasoning.text``, ``reasoning.summary``) and a text-carrying field
    (``text`` for reasoning.text, ``summary`` for reasoning.summary).

    This function returns None if the field is absent or empty.
    """
    details = getattr(delta, "reasoning_details", None)
    if not details:
        extras: dict | None = getattr(delta, "model_extra", None)
        if extras:
            details = extras.get("reasoning_details")
    if not details or not isinstance(details, list):
        return None

    parts: list[str] = []
    for item in details:
        if isinstance(item, dict):
            text: str = item.get("text", "") or item.get("summary", "") or ""
        else:
            text = getattr(item, "text", "") or getattr(item, "summary", "") or ""
        if text:
            parts.append(text)
    return "".join(parts) if parts else None


def _extract_delta_reasoning(delta) -> str | None:  # type: ignore[no-untyped-def]
    """Extract reasoning/thinking text from a streaming delta object.

    Tries two formats in order:

    1. Plain string fields (``reasoning_content`` / ``reasoning``) — used by the
       native DeepSeek API and some other providers.  Accessible as a direct
       attribute or via ``model_extra`` depending on SDK version.

    2. Structured ``reasoning_details`` array — used by OpenRouter for all
       providers it proxies (Anthropic, DeepSeek, OpenAI, etc.).  Each item in
       the array has a ``type`` (e.g. ``reasoning.text``) and a text field.
    """
    for field in _REASONING_FIELDS:
        # Path 1: direct attribute — works when SDK model uses extra='allow'
        val = getattr(delta, field, None)
        if val and isinstance(val, str):
            return val
        # Path 2: model_extra dict — Pydantic v2 fallback for non-standard fields
        extras: dict | None = getattr(delta, "model_extra", None)
        if extras:
            val = extras.get(field)
            if val and isinstance(val, str):
                return val

    # Path 3: reasoning_details array (OpenRouter)
    return _extract_delta_reasoning_details(delta)


def _delta_suffix(previous: str, current: str) -> str:
    """Return only the newly appended suffix when a provider repeats prior text."""
    if not current:
        return ""
    if previous and current.startswith(previous):
        return current[len(previous) :]
    return current


class LLMClient:
    """Async LLM client. All provider-specific wiring is encapsulated here.

    All SDKs are imported lazily so tests and imports that don't invoke the LLM
    never require the provider package to be installed.

    Thinking / reasoning is configured at construction time via:
        thinking_enabled  — master on/off toggle.
        thinking_budget   — token budget for Anthropic extended thinking.
        thinking_level    — reasoning effort for OpenAI o-series ("low"|"medium"|"high").

    When thinking_enabled=True but the selected model does not support it the
    client logs a warning and automatically retries without thinking params.
    """

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        api_key: str,
        api_base: str = "",
        thinking_enabled: bool = False,
        thinking_budget: int = 8000,
        thinking_level: str = "medium",
    ) -> None:
        self._provider = provider.lower()
        self._model = model
        self._api_key = api_key
        # Explicit api_base overrides the built-in provider default.
        self._api_base = api_base
        self._thinking_enabled = thinking_enabled
        # Anthropic: budget_tokens for extended thinking (enforced minimum of 1024).
        self._thinking_budget = max(1024, thinking_budget)
        # OpenAI o-series: reasoning_effort value.
        self._thinking_level = thinking_level

    @classmethod
    def from_settings(cls, s: Settings) -> LLMClient:
        return cls(
            provider=s.llm_provider,
            model=s.llm_model,
            api_key=s.llm_api_key,
            api_base=s.llm_api_base,
            thinking_enabled=s.llm_thinking_enabled,
            thinking_budget=s.llm_thinking_budget,
            thinking_level=s.llm_thinking_level,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.4,
        max_tokens: int = 4096,
        tools: Sequence[ProviderToolDefinition] | None = None,
    ) -> str:
        """Send a chat-completion request and return the assistant text."""
        if self._provider in _NATIVE_SDK_PROVIDERS:
            return await self._anthropic_chat(messages, temperature, max_tokens, tools=tools)
        if self._provider in _RESPONSES_API_PROVIDERS:
            return await self._openai_responses_chat(messages, temperature, max_tokens, tools=tools)
        return await self._openai_compatible_chat(messages, temperature, max_tokens, tools=tools)

    async def chat_stream(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Send a streaming chat request and yield text-only token chunks.

        Thinking/reasoning tokens are silently dropped.  Use chat_stream_tagged()
        if you need to distinguish text vs. thinking chunks.
        """
        async for kind, chunk in self.chat_stream_tagged(
            messages, temperature=temperature, max_tokens=max_tokens
        ):
            if kind == "text":
                yield chunk

    async def chat_stream_tagged(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.4,
        max_tokens: int = 4096,
        thinking: bool | None = None,
    ) -> AsyncIterator[TaggedChunk]:
        """Streaming chat that yields (kind, chunk) tuples.

        kind is "text" for normal output or "thinking" for reasoning tokens.

        Provider behaviour:
          openai      — Responses API; reasoning summaries stream as ("thinking", chunk)
                        only when thinking_enabled=True.
          openrouter  — Chat Completions; DeepSeek-R1 reasoning in reasoning_content/
                        reasoning delta field.
          anthropic   — Native SDK; thinking blocks stream as ("thinking", chunk).
        """
        requested_thinking = self._thinking_enabled if thinking is None else thinking
        if self._provider in _NATIVE_SDK_PROVIDERS:
            async for item in self._anthropic_chat_stream_tagged(
                messages,
                temperature,
                max_tokens,
                thinking=requested_thinking,
            ):
                yield item
        elif self._provider in _RESPONSES_API_PROVIDERS:
            async for item in self._openai_responses_chat_stream_tagged(
                messages,
                temperature,
                max_tokens,
                thinking=requested_thinking,
            ):
                yield item
        else:
            async for item in self._openai_compatible_chat_stream_tagged(
                messages,
                temperature,
                max_tokens,
                thinking=requested_thinking,
            ):
                yield item

    async def chat_stream_events(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.4,
        max_tokens: int = 4096,
        thinking: bool | None = None,
        tools: Sequence[ProviderToolDefinition] | None = None,
    ) -> AsyncIterator[NormalizedStreamEvent]:
        """Streaming chat normalized to text/thinking/tool events.

        This is the tool-aware path for future services. Existing tutor streaming
        still uses chat_stream_tagged() so public event behavior stays unchanged.
        """
        requested_thinking = self._thinking_enabled if thinking is None else thinking
        if self._provider in _NATIVE_SDK_PROVIDERS:
            async for item in self._anthropic_chat_stream_events(
                messages,
                temperature,
                max_tokens,
                thinking=requested_thinking,
                tools=tools,
            ):
                yield item
        elif self._provider in _RESPONSES_API_PROVIDERS:
            async for item in self._openai_responses_chat_stream_events(
                messages,
                temperature,
                max_tokens,
                thinking=requested_thinking,
                tools=tools,
            ):
                yield item
        else:
            async for item in self._openai_compatible_chat_stream_events(
                messages,
                temperature,
                max_tokens,
                thinking=requested_thinking,
                tools=tools,
            ):
                yield item

    # ------------------------------------------------------------------
    # OpenAI Responses API path  (provider == "openai")
    # ------------------------------------------------------------------

    def _build_responses_api_kwargs(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        thinking: bool | None = None,
        tools: Sequence[ProviderToolDefinition] | None = None,
    ) -> dict:
        """Convert a messages list to kwargs for client.responses.create.

        The Responses API accepts the same role/content dict format as Chat
        Completions under the ``input`` key.  System-role messages are extracted
        and passed separately as ``instructions`` for cleaner semantics, though
        leaving them in ``input`` also works.

        When ``thinking_enabled=True`` the request asks for a reasoning summary
        (``reasoning.summary='auto'``).  Reasoning models do not accept
        ``temperature``; it is omitted when thinking is enabled.
        """
        instructions = ""
        input_items: list[dict] = []
        for msg in messages:
            if msg.get("role") == "system":
                instructions = msg.get("content", "")
            else:
                input_items.append(msg)

        requested_thinking = self._thinking_enabled if thinking is None else thinking
        effective_max_tokens = (
            max_tokens + self._thinking_budget if requested_thinking else max_tokens
        )

        kwargs: dict = {
            "model": self._model,
            "input": input_items if input_items else messages,
            "max_output_tokens": effective_max_tokens,
            # Stateless: CoLearni manages its own context window.
            "store": False,
        }

        if instructions:
            kwargs["instructions"] = instructions

        if tools:
            kwargs["tools"] = openai_responses_tool_definitions(tools)

        if requested_thinking:
            # Reasoning models use effort instead of temperature.
            kwargs["reasoning"] = {
                "effort": self._thinking_level,  # low | medium | high
                "summary": "auto",  # surface the richest summary available
            }
        else:
            kwargs["temperature"] = temperature

        return kwargs

    async def _openai_responses_chat(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        *,
        tools: Sequence[ProviderToolDefinition] | None = None,
    ) -> str:
        """Non-streaming call via the OpenAI Responses API."""
        client = self._openai_client()
        kwargs = self._build_responses_api_kwargs(messages, temperature, max_tokens, tools=tools)
        response = await client.responses.create(**kwargs)
        # output_text is a convenience property that concatenates all text output.
        return response.output_text or ""

    async def _openai_responses_chat_stream_tagged(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        *,
        thinking: bool | None = None,
        tools: Sequence[ProviderToolDefinition] | None = None,
    ) -> AsyncIterator[TaggedChunk]:
        """Tagged streaming via the OpenAI Responses API.

        Yields:
          ("thinking", chunk)  — reasoning summary deltas
                                 (only when thinking_enabled=True; requires
                                  reasoning.summary='auto' on the request).
          ("text", chunk)      — output text deltas.

        Event types consumed:
          response.reasoning_summary_text.delta  — thinking
          response.output_text.delta             — text
        """
        client = self._openai_client()
        kwargs = self._build_responses_api_kwargs(
            messages,
            temperature,
            max_tokens,
            thinking=thinking,
            tools=tools,
        )
        kwargs["stream"] = True
        stream = await client.responses.create(**kwargs)
        async for event in stream:
            event_type: str = getattr(event, "type", "")
            delta: str = getattr(event, "delta", "") or ""
            if not delta:
                continue
            if event_type == "response.reasoning_summary_text.delta":
                logger.debug("Responses API: reasoning summary chunk (len=%d)", len(delta))
                yield ("thinking", delta)
            elif event_type == "response.output_text.delta":
                yield ("text", delta)

    async def _openai_responses_chat_stream_events(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        *,
        thinking: bool | None = None,
        tools: Sequence[ProviderToolDefinition] | None = None,
    ) -> AsyncIterator[NormalizedStreamEvent]:
        client = self._openai_client()
        kwargs = self._build_responses_api_kwargs(
            messages,
            temperature,
            max_tokens,
            thinking=thinking,
            tools=tools,
        )
        kwargs["stream"] = True
        stream = await client.responses.create(**kwargs)
        async for event in stream:
            normalized = normalize_openai_responses_stream_event(event, tools or ())
            if normalized is not None:
                yield normalized

    # ------------------------------------------------------------------
    # OpenAI-compatible path (OpenRouter, DeepSeek, Gemini, custom)
    # ------------------------------------------------------------------

    def _openai_base_url(self) -> str:
        if self._api_base:
            return self._api_base
        return PROVIDER_BASE_URLS.get(self._provider, "")

    def _openai_client(self):  # type: ignore[return]
        from openai import AsyncOpenAI  # lazy

        kwargs: dict = {"api_key": self._api_key}
        base_url = self._openai_base_url()
        if base_url:
            kwargs["base_url"] = base_url
        return AsyncOpenAI(**kwargs)

    def _openrouter_headers(self) -> dict:
        if self._provider == "openrouter":
            # OpenRouter recommends these for routing and analytics.
            return {"HTTP-Referer": "https://colearni.app", "X-Title": "CoLearni"}
        return {}

    def _build_openai_kwargs(
        self,
        messages: list[dict],
        temperature: float,
        *,
        thinking: bool,
        max_tokens: int = 4096,
        tools: Sequence[ProviderToolDefinition] | None = None,
    ) -> dict:
        """Build the kwargs dict for an OpenAI-compatible completions call.

        OpenRouter requires reasoning control via ``extra_body.reasoning`` rather
        than a top-level ``reasoning_effort`` parameter.

        - ``provider=openrouter`` with ``thinking=True``:
            ``extra_body={"reasoning": {"effort": level}}``
        - ``provider=openrouter`` with ``thinking=False``:
            ``extra_body={"reasoning": {"effort": "none"}}`` — explicitly disables
            default reasoning so the model does not reason unless opted in.

        For other Chat Completions providers the ``reasoning_effort`` top-level
        parameter is used when thinking is on (legacy OpenAI o-series behaviour).
        """
        effective_max_tokens = max_tokens + self._thinking_budget if thinking else max_tokens
        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "max_tokens": effective_max_tokens,
        }
        extra_headers = self._openrouter_headers()
        if extra_headers:
            kwargs["extra_headers"] = extra_headers

        if tools:
            kwargs["tools"] = openai_chat_tool_definitions(tools)

        if self._provider == "openrouter":
            # OpenRouter normalises reasoning across all its models via extra_body.
            # Always send an explicit effort level so the model's default reasoning
            # behaviour does not leak through when the user has not opted in.
            kwargs["extra_body"] = {
                "reasoning": {"effort": self._thinking_level if thinking else "none"}
            }
            kwargs["temperature"] = temperature
        elif thinking:
            # o-series Chat Completions (openai provider now uses Responses API,
            # but keep this for custom/other providers that mirror o-series).
            kwargs["reasoning_effort"] = self._thinking_level
            # temperature must be omitted for o-series
        else:
            kwargs["temperature"] = temperature
        return kwargs

    async def _openai_compatible_chat(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int = 4096,
        *,
        tools: Sequence[ProviderToolDefinition] | None = None,
    ) -> str:
        client = self._openai_client()
        kwargs = self._build_openai_kwargs(
            messages,
            temperature,
            thinking=self._thinking_enabled,
            max_tokens=max_tokens,
            tools=tools,
        )
        try:
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""
        except Exception as exc:
            if self._thinking_enabled and _is_thinking_error(exc):
                logger.warning(
                    "Thinking not supported by model %r; retrying without. Error: %s",
                    self._model,
                    exc,
                )
                kwargs = self._build_openai_kwargs(
                    messages,
                    temperature,
                    thinking=False,
                    max_tokens=max_tokens,
                    tools=tools,
                )
                response = await client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""
            raise

    async def _openai_compatible_chat_stream(
        self, messages: list[dict], temperature: float, max_tokens: int = 4096
    ) -> AsyncIterator[str]:
        """Text-only OpenAI-compatible stream. Reasoning tokens are dropped."""
        async for kind, chunk in self._openai_compatible_chat_stream_tagged(
            messages, temperature, max_tokens
        ):
            if kind == "text":
                yield chunk

    async def _openai_compatible_chat_stream_tagged(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int = 4096,
        *,
        thinking: bool | None = None,
        tools: Sequence[ProviderToolDefinition] | None = None,
    ) -> AsyncIterator[TaggedChunk]:
        """Tagged OpenAI-compatible stream.

        Yields ("text", chunk) for regular content and ("thinking", chunk) for
        reasoning tokens.  Uses _extract_delta_reasoning() to handle the
        provider-specific field names and SDK storage differences.

        Reasoning tokens are always forwarded when the model emits them.
        ``thinking_enabled`` controls whether reasoning is *requested* from the
        model; it does not suppress tokens the model chooses to emit.
        """
        client = self._openai_client()
        requested_thinking = self._thinking_enabled if thinking is None else thinking
        kwargs = self._build_openai_kwargs(
            messages,
            temperature,
            thinking=requested_thinking,
            max_tokens=max_tokens,
            tools=tools,
        )
        kwargs["stream"] = True
        reasoning_so_far = ""
        try:
            stream = await client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                reasoning = _extract_delta_reasoning(delta)
                if reasoning:
                    next_reasoning = _delta_suffix(reasoning_so_far, reasoning)
                    if next_reasoning:
                        logger.debug("Reasoning chunk received (len=%d)", len(next_reasoning))
                        yield ("thinking", next_reasoning)
                    reasoning_so_far = _next_reasoning_so_far(reasoning_so_far, reasoning)
                if delta.content:
                    yield ("text", delta.content)
        except Exception as exc:
            if requested_thinking and _is_thinking_error(exc):
                logger.warning(
                    "Thinking not supported by model %r; retrying without. Error: %s",
                    self._model,
                    exc,
                )
                kwargs = self._build_openai_kwargs(
                    messages,
                    temperature,
                    thinking=False,
                    max_tokens=max_tokens,
                    tools=tools,
                )
                kwargs["stream"] = True
                stream = await client.chat.completions.create(**kwargs)
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    reasoning = _extract_delta_reasoning(delta)
                    if reasoning:
                        next_reasoning = _delta_suffix(reasoning_so_far, reasoning)
                        if next_reasoning:
                            logger.debug("Reasoning chunk received (len=%d)", len(next_reasoning))
                            yield ("thinking", next_reasoning)
                        reasoning_so_far = _next_reasoning_so_far(reasoning_so_far, reasoning)
                    if delta.content:
                        yield ("text", delta.content)
            else:
                raise

    async def _openai_compatible_chat_stream_events(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int = 4096,
        *,
        thinking: bool | None = None,
        tools: Sequence[ProviderToolDefinition] | None = None,
    ) -> AsyncIterator[NormalizedStreamEvent]:
        client = self._openai_client()
        requested_thinking = self._thinking_enabled if thinking is None else thinking
        kwargs = self._build_openai_kwargs(
            messages,
            temperature,
            thinking=requested_thinking,
            max_tokens=max_tokens,
            tools=tools,
        )
        kwargs["stream"] = True
        reasoning_so_far = ""
        tool_call_parts: dict[int, dict] = {}
        try:
            stream = await client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                reasoning = _extract_delta_reasoning(delta)
                if reasoning:
                    next_reasoning = _delta_suffix(reasoning_so_far, reasoning)
                    if next_reasoning:
                        yield NormalizedStreamEvent.thinking_delta(next_reasoning)
                    reasoning_so_far = (
                        reasoning
                        if len(reasoning) >= len(reasoning_so_far)
                        else reasoning_so_far + reasoning
                    )
                for event in normalize_openai_chat_stream_chunk(chunk, tools or ()):
                    if event.kind != "tool_call":
                        yield event
                _accumulate_openai_chat_tool_call_deltas(delta, tool_call_parts)
                if getattr(choice, "finish_reason", None) == "tool_calls":
                    for item in tool_call_parts.values():
                        yield NormalizedStreamEvent.tool_call_event(
                            normalize_openai_chat_tool_call(item, tools or ())
                    )
                    tool_call_parts.clear()
            yield NormalizedStreamEvent.done_event()
        except Exception as exc:
            if requested_thinking and _is_thinking_error(exc):
                logger.warning(
                    "Thinking not supported by model %r; retrying without. Error: %s",
                    self._model,
                    exc,
                )
                kwargs = self._build_openai_kwargs(
                    messages,
                    temperature,
                    thinking=False,
                    max_tokens=max_tokens,
                    tools=tools,
                )
                kwargs["stream"] = True
                stream = await client.chat.completions.create(**kwargs)
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    choice = chunk.choices[0]
                    delta = choice.delta
                    for event in normalize_openai_chat_stream_chunk(chunk, tools or ()):
                        if event.kind != "tool_call":
                            yield event
                    _accumulate_openai_chat_tool_call_deltas(delta, tool_call_parts)
                    if getattr(choice, "finish_reason", None) == "tool_calls":
                        for item in tool_call_parts.values():
                            yield NormalizedStreamEvent.tool_call_event(
                                normalize_openai_chat_tool_call(item, tools or ())
                            )
                        tool_call_parts.clear()
                yield NormalizedStreamEvent.done_event()
            else:
                raise

    # ------------------------------------------------------------------
    # Anthropic native path
    # ------------------------------------------------------------------

    def _anthropic_client(self):  # type: ignore[return]
        from anthropic import AsyncAnthropic  # lazy

        return AsyncAnthropic(api_key=self._api_key)

    def _build_anthropic_kwargs(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        *,
        thinking: bool,
        tools: Sequence[ProviderToolDefinition] | None = None,
    ) -> tuple[dict, list[dict]]:
        """Return (kwargs, turns) for an Anthropic messages call.

        Extended thinking requires temperature=1 and budget_tokens >= 1024.
        When thinking=True those constraints are applied automatically.
        Text blocks are always returned by the response; the caller should
        filter for type=="text" to skip any thinking blocks.
        """
        system = ""
        turns: list[dict] = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                turns.append(msg)

        # When thinking is on, max_tokens must cover budget + useful output.
        effective_max_tokens = (
            max(max_tokens, self._thinking_budget + 1024) if thinking else max_tokens
        )

        kwargs: dict = {
            "model": self._model,
            "max_tokens": effective_max_tokens,
            "messages": turns,
        }
        if system:
            kwargs["system"] = system

        if tools:
            kwargs["tools"] = anthropic_tool_definitions(tools)

        if thinking:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": self._thinking_budget}
            kwargs["temperature"] = 1  # required by Anthropic when thinking is enabled
        else:
            kwargs["temperature"] = temperature

        return kwargs, turns

    async def _anthropic_chat(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        *,
        tools: Sequence[ProviderToolDefinition] | None = None,
    ) -> str:
        client = self._anthropic_client()
        kwargs, _ = self._build_anthropic_kwargs(
            messages,
            temperature,
            max_tokens,
            thinking=self._thinking_enabled,
            tools=tools,
        )
        try:
            response = await client.messages.create(**kwargs)
        except Exception as exc:
            if self._thinking_enabled and _is_thinking_error(exc):
                logger.warning(
                    "Thinking not supported by model %r; retrying without. Error: %s",
                    self._model,
                    exc,
                )
                kwargs, _ = self._build_anthropic_kwargs(
                    messages,
                    temperature,
                    max_tokens,
                    thinking=False,
                    tools=tools,
                )
                response = await client.messages.create(**kwargs)
            else:
                raise
        # Filter to text blocks only; extended thinking adds thinking-type blocks.
        return "".join(b.text for b in response.content if b.type == "text")

    async def _anthropic_chat_stream(
        self, messages: list[dict], temperature: float, max_tokens: int
    ) -> AsyncIterator[str]:
        """Text-only Anthropic stream (thinking blocks filtered out).

        Delegates to _anthropic_chat_stream_tagged and drops thinking chunks.
        """
        async for kind, chunk in self._anthropic_chat_stream_tagged(
            messages, temperature, max_tokens
        ):
            if kind == "text":
                yield chunk

    async def _anthropic_chat_stream_tagged(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        *,
        thinking: bool | None = None,
        tools: Sequence[ProviderToolDefinition] | None = None,
    ) -> AsyncIterator[TaggedChunk]:
        """Anthropic stream that yields (kind, chunk) tuples.

        Iterates raw stream events so that thinking_delta blocks produce
        ("thinking", ...) and text_delta blocks produce ("text", ...).
        Falls back to text-only streaming when thinking is not supported.
        """
        client = self._anthropic_client()
        requested_thinking = self._thinking_enabled if thinking is None else thinking
        kwargs, _ = self._build_anthropic_kwargs(
            messages,
            temperature,
            max_tokens,
            thinking=requested_thinking,
            tools=tools,
        )
        try:
            async with client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if event.type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "thinking_delta":
                            yield ("thinking", delta.thinking)
                        elif delta.type == "text_delta":
                            yield ("text", delta.text)
        except Exception as exc:
            if requested_thinking and _is_thinking_error(exc):
                logger.warning(
                    "Thinking not supported by model %r; retrying without. Error: %s",
                    self._model,
                    exc,
                )
                kwargs, _ = self._build_anthropic_kwargs(
                    messages,
                    temperature,
                    max_tokens,
                    thinking=False,
                    tools=tools,
                )
                async with client.messages.stream(**kwargs) as stream:
                    async for text in stream.text_stream:
                        yield ("text", text)
            else:
                raise

    async def _anthropic_chat_stream_events(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        *,
        thinking: bool | None = None,
        tools: Sequence[ProviderToolDefinition] | None = None,
    ) -> AsyncIterator[NormalizedStreamEvent]:
        client = self._anthropic_client()
        requested_thinking = self._thinking_enabled if thinking is None else thinking
        kwargs, _ = self._build_anthropic_kwargs(
            messages,
            temperature,
            max_tokens,
            thinking=requested_thinking,
            tools=tools,
        )
        try:
            state = AnthropicStreamState()
            async with client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    normalized = normalize_anthropic_stream_event(event, tools or (), state)
                    if normalized is not None:
                        yield normalized
        except Exception as exc:
            if requested_thinking and _is_thinking_error(exc):
                logger.warning(
                    "Thinking not supported by model %r; retrying without. Error: %s",
                    self._model,
                    exc,
                )
                kwargs, _ = self._build_anthropic_kwargs(
                    messages,
                    temperature,
                    max_tokens,
                    thinking=False,
                    tools=tools,
                )
                state = AnthropicStreamState()
                async with client.messages.stream(**kwargs) as stream:
                    async for event in stream:
                        normalized = normalize_anthropic_stream_event(event, tools or (), state)
                        if normalized is not None:
                            yield normalized
            else:
                raise


def _accumulate_openai_chat_tool_call_deltas(  # type: ignore[no-untyped-def]
    delta,
    parts: dict[int, dict],
) -> None:
    for tool_call in getattr(delta, "tool_calls", None) or []:
        index = getattr(tool_call, "index", None)
        if index is None:
            index = len(parts)
        item = parts.setdefault(index, {"id": "", "function": {"name": "", "arguments": ""}})
        call_id = getattr(tool_call, "id", None)
        if call_id:
            item["id"] = call_id
        function = getattr(tool_call, "function", None)
        if function is None:
            continue
        name = getattr(function, "name", None)
        if name:
            item["function"]["name"] = name
        arguments = getattr(function, "arguments", None)
        if arguments:
            item["function"]["arguments"] += arguments


def _next_reasoning_so_far(previous: str, current: str) -> str:
    return current if len(current) >= len(previous) else previous + current
