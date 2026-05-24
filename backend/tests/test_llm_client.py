"""Unit tests for LLMClient thinking/reasoning configuration.

These tests never call a real LLM — they verify that:
  1. Thinking params are correctly wired from Settings.
  2. Anthropic, OpenAI Responses API, and Chat Completions kwargs are built correctly.
  3. The graceful fallback fires when a thinking-related error is raised.
  4. Non-thinking path is unchanged when thinking is disabled.
  5. Provider routing sends openai to Responses API, others to Chat Completions.
"""

from __future__ import annotations

from typing import Any

import pytest

from backend.app.agents.llm_client import LLMClient, _is_thinking_error
from backend.app.agents.provider_tools import (
    AnthropicStreamState,
    NormalizedStreamEvent,
    NormalizedToolResult,
    ProviderToolDefinition,
    normalize_anthropic_stream_event,
    normalize_anthropic_tool_call,
    normalize_anthropic_tool_result,
    normalize_openai_chat_tool_call,
    normalize_openai_chat_tool_result,
    normalize_openai_responses_tool_call,
    normalize_openai_responses_tool_result,
)
from backend.app.settings import Settings

# ---------------------------------------------------------------------------
# Helper: build a client directly without Settings
# ---------------------------------------------------------------------------


def make_client(**kwargs: Any) -> LLMClient:
    return LLMClient(
        provider=kwargs.get("provider", "openai"),
        model=kwargs.get("model", "gpt-4o-mini"),
        api_key=kwargs.get("api_key", "test-key"),
        api_base=kwargs.get("api_base", ""),
        thinking_enabled=kwargs.get("thinking_enabled", False),
        thinking_budget=kwargs.get("thinking_budget", 8000),
        thinking_level=kwargs.get("thinking_level", "medium"),
    )


def tutor_tool_definition() -> ProviderToolDefinition:
    return ProviderToolDefinition(
        name="get_tutor_instructions",
        description="Return tutor instructions.",
        parameters={
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["direct", "free_explore"]},
            },
            "required": ["mode"],
            "additionalProperties": False,
        },
        public_argument_fields=("mode",),
    )


# ---------------------------------------------------------------------------
# _is_thinking_error
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "msg,expected",
    [
        ("Invalid parameter: reasoning_effort", True),
        ("Unsupported thinking parameter", True),
        ("budget_tokens too small", True),
        ("Unauthorized: invalid api key", False),
        ("context length exceeded", False),
    ],
)
def test_is_thinking_error(msg: str, expected: bool):
    assert _is_thinking_error(ValueError(msg)) is expected


# ---------------------------------------------------------------------------
# Settings → LLMClient wiring
# ---------------------------------------------------------------------------


def test_from_settings_thinking_defaults():
    s = Settings(
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        llm_api_key="k",
        llm_thinking_enabled=False,
        llm_thinking_budget=8000,
        llm_thinking_level="medium",
    )
    client = LLMClient.from_settings(s)
    assert client._thinking_enabled is False
    assert client._thinking_budget == 8000
    assert client._thinking_level == "medium"


def test_from_settings_thinking_enabled():
    s = Settings(
        llm_provider="anthropic",
        llm_model="claude-3-7-sonnet-20250219",
        llm_api_key="k",
        llm_thinking_enabled=True,
        llm_thinking_budget=5000,
        llm_thinking_level="high",
    )
    client = LLMClient.from_settings(s)
    assert client._thinking_enabled is True
    assert client._thinking_budget == 5000
    assert client._thinking_level == "high"


def test_thinking_budget_minimum_enforced():
    client = make_client(thinking_enabled=True, thinking_budget=100)
    assert client._thinking_budget == 1024  # enforced minimum


# ---------------------------------------------------------------------------
# Anthropic kwargs builder
# ---------------------------------------------------------------------------


def test_anthropic_kwargs_no_thinking():
    client = make_client(provider="anthropic", thinking_enabled=False)
    messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
    kwargs, turns = client._build_anthropic_kwargs(
        messages, temperature=0.4, max_tokens=4096, thinking=False
    )

    assert kwargs["temperature"] == 0.4
    assert kwargs["max_tokens"] == 4096
    assert kwargs["system"] == "sys"
    assert "thinking" not in kwargs
    assert turns == [{"role": "user", "content": "hi"}]


def test_anthropic_kwargs_registers_normalized_tools():
    client = make_client(provider="anthropic", thinking_enabled=False)
    tool = tutor_tool_definition()
    kwargs, _ = client._build_anthropic_kwargs(
        [{"role": "user", "content": "hi"}],
        temperature=0.4,
        max_tokens=4096,
        thinking=False,
        tools=[tool],
    )

    assert kwargs["tools"] == [
        {
            "name": "get_tutor_instructions",
            "description": "Return tutor instructions.",
            "input_schema": tool.parameters,
        }
    ]


def test_anthropic_kwargs_with_thinking():
    client = make_client(provider="anthropic", thinking_enabled=True, thinking_budget=3000)
    messages = [{"role": "user", "content": "hi"}]
    kwargs, _ = client._build_anthropic_kwargs(
        messages, temperature=0.4, max_tokens=4096, thinking=True
    )

    assert kwargs["temperature"] == 1  # required by Anthropic when thinking on
    assert kwargs["thinking"] == {"type": "enabled", "budget_tokens": 3000}
    # budget(3000) + 1024 = 4024 < max_tokens(4096), so max_tokens stays at 4096
    assert kwargs["max_tokens"] == 4096


def test_anthropic_kwargs_thinking_bumps_max_tokens():
    client = make_client(provider="anthropic", thinking_enabled=True, thinking_budget=8000)
    messages = [{"role": "user", "content": "hi"}]
    kwargs, _ = client._build_anthropic_kwargs(
        messages, temperature=0.4, max_tokens=2000, thinking=True
    )
    # 2000 < 8000 + 1024 so max_tokens should be bumped
    assert kwargs["max_tokens"] == 9024


def test_anthropic_kwargs_no_system_key_when_empty():
    client = make_client(provider="anthropic", thinking_enabled=False)
    messages = [{"role": "user", "content": "hi"}]
    kwargs, _ = client._build_anthropic_kwargs(
        messages, temperature=0.4, max_tokens=4096, thinking=False
    )
    assert "system" not in kwargs


# ---------------------------------------------------------------------------
# OpenAI-compatible kwargs builder
# ---------------------------------------------------------------------------


def test_openai_kwargs_no_thinking():
    client = make_client(provider="deepseek", thinking_enabled=False)
    kwargs = client._build_openai_kwargs(
        [{"role": "user", "content": "hi"}], temperature=0.4, thinking=False
    )
    assert kwargs["temperature"] == 0.4
    assert "reasoning_effort" not in kwargs


def test_openai_chat_kwargs_registers_normalized_tools():
    client = make_client(provider="openrouter", thinking_enabled=False)
    tool = tutor_tool_definition()
    kwargs = client._build_openai_kwargs(
        [{"role": "user", "content": "hi"}],
        temperature=0.4,
        thinking=False,
        tools=[tool],
    )

    assert kwargs["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "get_tutor_instructions",
                "description": "Return tutor instructions.",
                "parameters": tool.parameters,
            },
        }
    ]


def test_openai_kwargs_with_thinking():
    client = make_client(provider="deepseek", thinking_enabled=True, thinking_level="low")
    kwargs = client._build_openai_kwargs(
        [{"role": "user", "content": "hi"}], temperature=0.4, thinking=True
    )
    assert kwargs["reasoning_effort"] == "low"
    # temperature must be omitted for o-series
    assert "temperature" not in kwargs


def test_openrouter_headers_included():
    client = make_client(provider="openrouter", thinking_enabled=False)
    kwargs = client._build_openai_kwargs(
        [{"role": "user", "content": "hi"}], temperature=0.4, thinking=False
    )
    assert "extra_headers" in kwargs
    assert kwargs["extra_headers"]["X-Title"] == "CoLearni"


def test_openai_compatible_kwargs_include_max_tokens():
    client = make_client(provider="openrouter", thinking_enabled=True)
    kwargs = client._build_openai_kwargs(
        [{"role": "user", "content": "hi"}],
        temperature=0.4,
        thinking=True,
        max_tokens=12000,
    )
    assert kwargs["max_tokens"] == 20000


def test_openrouter_disables_reasoning_when_thinking_off():
    """When thinking_enabled=False, OpenRouter kwargs must include effort=none."""
    client = make_client(provider="openrouter", thinking_enabled=False)
    kwargs = client._build_openai_kwargs(
        [{"role": "user", "content": "hi"}], temperature=0.4, thinking=False
    )
    assert kwargs["extra_body"] == {"reasoning": {"effort": "none"}}
    assert kwargs["temperature"] == 0.4


def test_openrouter_enables_reasoning_with_effort_when_thinking_on():
    """When thinking_enabled=True, OpenRouter kwargs must include effort=level."""
    client = make_client(provider="openrouter", thinking_enabled=True, thinking_level="high")
    kwargs = client._build_openai_kwargs(
        [{"role": "user", "content": "hi"}], temperature=0.4, thinking=True
    )
    assert kwargs["extra_body"] == {"reasoning": {"effort": "high"}}
    # temperature is still included for OpenRouter (unlike raw o-series)
    assert kwargs["temperature"] == 0.4


def test_non_openrouter_no_extra_headers():
    client = make_client(provider="deepseek", thinking_enabled=False)
    kwargs = client._build_openai_kwargs(
        [{"role": "user", "content": "hi"}], temperature=0.4, thinking=False
    )
    assert "extra_headers" not in kwargs


# ---------------------------------------------------------------------------
# Graceful fallback: OpenAI-compatible chat (mocked)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_openai_chat_falls_back_on_thinking_error(monkeypatch):
    """When the API rejects reasoning_effort the client retries without it."""
    calls: list[dict] = []

    class FakeMessage:
        content = "ok"

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    async def fake_create(**kwargs):
        calls.append(dict(kwargs))
        if "reasoning_effort" in kwargs:
            raise ValueError("Unsupported parameter: reasoning_effort")
        return FakeResponse()

    client = make_client(provider="openai", thinking_enabled=True, thinking_level="medium")

    # Patch the internal OpenAI client
    class FakeOAIClient:
        class chat:
            class completions:
                create = staticmethod(fake_create)

    monkeypatch.setattr(client, "_openai_client", lambda: FakeOAIClient())

    result = await client._openai_compatible_chat(
        [{"role": "user", "content": "hi"}], temperature=0.4
    )

    assert result == "ok"
    # First call had reasoning_effort, second did not
    assert "reasoning_effort" in calls[0]
    assert "reasoning_effort" not in calls[1]
    assert calls[1]["temperature"] == 0.4


@pytest.mark.anyio
async def test_openai_chat_reraises_non_thinking_error(monkeypatch):
    """Non-thinking errors must not be swallowed."""

    async def fake_create(**kwargs):
        raise ValueError("context length exceeded")

    class FakeOAIClient:
        class chat:
            class completions:
                create = staticmethod(fake_create)

    client = make_client(provider="openai", thinking_enabled=True)
    monkeypatch.setattr(client, "_openai_client", lambda: FakeOAIClient())

    with pytest.raises(ValueError, match="context length exceeded"):
        await client._openai_compatible_chat([{"role": "user", "content": "hi"}], temperature=0.4)


# ---------------------------------------------------------------------------
# OpenAI Responses API kwargs builder
# ---------------------------------------------------------------------------


def test_responses_api_kwargs_no_thinking():
    client = make_client(provider="openai", thinking_enabled=False)
    messages = [{"role": "user", "content": "hi"}]
    kwargs = client._build_responses_api_kwargs(messages, temperature=0.5, max_tokens=2048)

    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["input"] == messages
    assert kwargs["temperature"] == 0.5
    assert kwargs["max_output_tokens"] == 2048
    assert kwargs["store"] is False
    assert "reasoning" not in kwargs


def test_responses_api_kwargs_registers_normalized_tools():
    client = make_client(provider="openai", thinking_enabled=False)
    tool = tutor_tool_definition()

    kwargs = client._build_responses_api_kwargs(
        [{"role": "user", "content": "hi"}],
        temperature=0.4,
        max_tokens=1024,
        tools=[tool],
    )

    assert kwargs["tools"] == [
        {
            "type": "function",
            "name": "get_tutor_instructions",
            "description": "Return tutor instructions.",
            "parameters": tool.parameters,
        }
    ]


def test_responses_api_kwargs_with_thinking():
    client = make_client(provider="openai", thinking_enabled=True, thinking_level="high")
    messages = [{"role": "user", "content": "hi"}]
    kwargs = client._build_responses_api_kwargs(messages, temperature=0.5, max_tokens=2048)

    # Temperature must be omitted when reasoning is requested
    assert "temperature" not in kwargs
    assert kwargs["reasoning"] == {"effort": "high", "summary": "auto"}


def test_responses_api_kwargs_extracts_system_message():
    client = make_client(provider="openai", thinking_enabled=False)
    messages = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "hi"},
    ]
    kwargs = client._build_responses_api_kwargs(messages, temperature=0.4, max_tokens=1024)

    assert kwargs["instructions"] == "Be concise."
    # System message must not appear in input
    assert kwargs["input"] == [{"role": "user", "content": "hi"}]


def test_responses_api_kwargs_no_instructions_when_no_system():
    client = make_client(provider="openai", thinking_enabled=False)
    messages = [{"role": "user", "content": "hi"}]
    kwargs = client._build_responses_api_kwargs(messages, temperature=0.4, max_tokens=1024)

    assert "instructions" not in kwargs


# ---------------------------------------------------------------------------
# _extract_delta_reasoning_details: OpenRouter reasoning_details array
# ---------------------------------------------------------------------------


def test_extract_reasoning_details_reasoning_text_type():
    from backend.app.agents.llm_client import _extract_delta_reasoning_details

    class FakeDelta:
        reasoning_details = [{"type": "reasoning.text", "text": "I think...", "index": 0}]
        model_extra = None

    assert _extract_delta_reasoning_details(FakeDelta()) == "I think..."


def test_extract_reasoning_details_reasoning_summary_type():
    from backend.app.agents.llm_client import _extract_delta_reasoning_details

    class FakeDelta:
        reasoning_details = [{"type": "reasoning.summary", "summary": "Summarised.", "index": 0}]
        model_extra = None

    assert _extract_delta_reasoning_details(FakeDelta()) == "Summarised."


def test_extract_reasoning_details_concatenates_multiple():
    from backend.app.agents.llm_client import _extract_delta_reasoning_details

    class FakeDelta:
        reasoning_details = [
            {"type": "reasoning.text", "text": "Step 1. "},
            {"type": "reasoning.text", "text": "Step 2."},
        ]
        model_extra = None

    assert _extract_delta_reasoning_details(FakeDelta()) == "Step 1. Step 2."


def test_extract_reasoning_details_none_when_absent():
    from backend.app.agents.llm_client import _extract_delta_reasoning_details

    class FakeDelta:
        reasoning_details = None
        model_extra = None

    assert _extract_delta_reasoning_details(FakeDelta()) is None


def test_extract_delta_reasoning_falls_through_to_details():
    """_extract_delta_reasoning must reach reasoning_details when string fields are absent."""
    from backend.app.agents.llm_client import _extract_delta_reasoning

    class FakeDelta:
        reasoning_details = [{"type": "reasoning.text", "text": "via details"}]
        model_extra = None
        # No reasoning_content or reasoning string fields

    assert _extract_delta_reasoning(FakeDelta()) == "via details"


def test_delta_suffix_returns_only_new_reasoning_content():
    from backend.app.agents.llm_client import _delta_suffix

    assert (
        _delta_suffix("We need to decide.", "We need to decide. Then call the tool.")
        == " Then call the tool."
    )
    assert _delta_suffix("", "Fresh reasoning") == "Fresh reasoning"


# ---------------------------------------------------------------------------
# Reasoning observability: tokens always forwarded
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_reasoning_tokens_always_forwarded_regardless_of_thinking_flag(monkeypatch):
    """Reasoning tokens emitted by the model must always be forwarded.

    thinking_enabled controls whether reasoning is *requested*; it must not
    suppress tokens the model chooses to emit.  Observability comes first.
    """

    class FakeDelta:
        """Simulates a DeepSeek delta that includes reasoning_content."""

        reasoning_content = "I am thinking..."
        content = "Hello"
        model_extra = None

    class FakeChunk:
        choices = [type("C", (), {"delta": FakeDelta()})()]

    async def fake_stream():
        yield FakeChunk()

    async def fake_create(**kwargs):
        return fake_stream()

    class FakeOAIClient:
        class chat:
            class completions:
                create = staticmethod(fake_create)

    for thinking_enabled in (False, True):
        client = make_client(provider="openrouter", thinking_enabled=thinking_enabled)
        monkeypatch.setattr(client, "_openai_client", lambda: FakeOAIClient())

        chunks = []
        async for kind, chunk in client.chat_stream_tagged([{"role": "user", "content": "hi"}]):
            chunks.append((kind, chunk))

        # Reasoning tokens must be forwarded in both cases
        assert ("thinking", "I am thinking...") in chunks, (
            f"Reasoning token dropped when thinking_enabled={thinking_enabled}"
        )
        assert ("text", "Hello") in chunks


# ---------------------------------------------------------------------------
# Provider routing: openai → Responses API, others → Chat Completions
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_openai_provider_uses_responses_api(monkeypatch):
    """chat() must call client.responses.create for provider=openai."""
    responses_called = []
    completions_called = []

    class FakeResponse:
        output_text = "hello from responses"

    async def fake_responses_create(**kwargs):
        responses_called.append(kwargs)
        return FakeResponse()

    async def fake_completions_create(**kwargs):
        completions_called.append(kwargs)
        return type(
            "R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": "x"})()})()]}
        )()

    class FakeOAIClient:
        class responses:
            create = staticmethod(fake_responses_create)

        class chat:
            class completions:
                create = staticmethod(fake_completions_create)

    client = make_client(provider="openai", thinking_enabled=False)
    monkeypatch.setattr(client, "_openai_client", lambda: FakeOAIClient())

    result = await client.chat([{"role": "user", "content": "hi"}])

    assert result == "hello from responses"
    assert len(responses_called) == 1
    assert len(completions_called) == 0


@pytest.mark.anyio
async def test_openrouter_provider_uses_chat_completions(monkeypatch):
    """chat() must use Chat Completions for non-openai OpenAI-compatible providers."""
    responses_called = []
    completions_called = []

    async def fake_responses_create(**kwargs):
        responses_called.append(kwargs)

    async def fake_completions_create(**kwargs):
        completions_called.append(kwargs)
        return type(
            "R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": "x"})()})()]}
        )()

    class FakeOAIClient:
        class responses:
            create = staticmethod(fake_responses_create)

        class chat:
            class completions:
                create = staticmethod(fake_completions_create)

    client = make_client(provider="openrouter", thinking_enabled=False)
    monkeypatch.setattr(client, "_openai_client", lambda: FakeOAIClient())

    await client.chat([{"role": "user", "content": "hi"}])

    assert len(responses_called) == 0
    assert len(completions_called) == 1


@pytest.mark.anyio
async def test_responses_api_stream_yields_text_and_thinking(monkeypatch):
    """Streaming must yield (text, ...) and (thinking, ...) from the right event types."""

    class FakeEvent:
        def __init__(self, event_type: str, delta: str):
            self.type = event_type
            self.delta = delta

    fake_events = [
        FakeEvent("response.reasoning_summary_text.delta", "I think..."),
        FakeEvent("response.output_text.delta", "Hello"),
        FakeEvent("response.output_text.delta", " world"),
        FakeEvent("response.created", ""),  # no delta — should be skipped
    ]

    async def fake_aiter(self):
        for ev in fake_events:
            yield ev

    class FakeStream:
        def __aiter__(self):
            return fake_aiter(self)

    async def fake_responses_create(**kwargs):
        return FakeStream()

    class FakeOAIClient:
        class responses:
            create = staticmethod(fake_responses_create)

    client = make_client(provider="openai", thinking_enabled=True)
    monkeypatch.setattr(client, "_openai_client", lambda: FakeOAIClient())

    chunks = []
    async for kind, chunk in client.chat_stream_tagged([{"role": "user", "content": "hi"}]):
        chunks.append((kind, chunk))

    assert chunks == [
        ("thinking", "I think..."),
        ("text", "Hello"),
        ("text", " world"),
        # response.created skipped (no delta)
    ]


@pytest.mark.anyio
async def test_openai_compatible_stream_events_emit_done(monkeypatch):
    class FakeDelta:
        content = "Hello"
        model_extra = None

    class FakeChoice:
        delta = FakeDelta()
        finish_reason = "stop"

    class FakeChunk:
        choices = [FakeChoice()]

    async def fake_stream():
        yield FakeChunk()

    async def fake_create(**kwargs):
        return fake_stream()

    class FakeOAIClient:
        class chat:
            class completions:
                create = staticmethod(fake_create)

    client = make_client(provider="openrouter", thinking_enabled=False)
    monkeypatch.setattr(client, "_openai_client", lambda: FakeOAIClient())

    events = [
        event
        async for event in client.chat_stream_events([{"role": "user", "content": "hi"}])
    ]

    assert [event.kind for event in events] == ["text", "done"]
    assert events[0].text == "Hello"


# ---------------------------------------------------------------------------
# Provider-tool normalization
# ---------------------------------------------------------------------------


def test_openai_responses_tool_call_normalizes_to_internal_shape():
    call = normalize_openai_responses_tool_call(
        {
            "type": "function_call",
            "call_id": "call_1",
            "name": "get_tutor_instructions",
            "arguments": '{"mode":"direct"}',
        },
        [tutor_tool_definition()],
    )

    assert call.call_id == "call_1"
    assert call.name == "get_tutor_instructions"
    assert call.arguments == {"mode": "direct"}
    assert call.provider == "openai_responses"
    assert call.validation_error is None


def test_openai_responses_tool_result_normalizes_to_internal_shape():
    result = normalize_openai_responses_tool_result(
        {"call_id": "call_1", "output": "hidden instructions"},
        name="get_tutor_instructions",
        public_preview={"status": "received", "mode": "direct"},
    )

    assert result.call_id == "call_1"
    assert result.name == "get_tutor_instructions"
    assert result.content == "hidden instructions"
    assert result.public_preview == {"status": "received", "mode": "direct"}


def test_openai_chat_tool_call_normalizes_to_internal_shape():
    call = normalize_openai_chat_tool_call(
        {
            "id": "chat_call_1",
            "type": "function",
            "function": {
                "name": "get_tutor_instructions",
                "arguments": '{"mode":"free_explore"}',
            },
        },
        [tutor_tool_definition()],
    )

    assert call.call_id == "chat_call_1"
    assert call.name == "get_tutor_instructions"
    assert call.arguments == {"mode": "free_explore"}
    assert call.provider == "openai_chat"
    assert call.validation_error is None


def test_openai_chat_tool_result_normalizes_to_internal_shape():
    result = normalize_openai_chat_tool_result(
        {"role": "tool", "tool_call_id": "chat_call_1", "content": "hidden instructions"},
        name="get_tutor_instructions",
        public_preview={"status": "received", "mode": "free_explore"},
    )

    assert result.call_id == "chat_call_1"
    assert result.name == "get_tutor_instructions"
    assert result.content == "hidden instructions"
    assert result.public_preview == {"status": "received", "mode": "free_explore"}


def test_anthropic_tool_use_normalizes_to_internal_shape():
    call = normalize_anthropic_tool_call(
        {
            "type": "tool_use",
            "id": "anthropic_call_1",
            "name": "get_tutor_instructions",
            "input": {"mode": "direct"},
        },
        [tutor_tool_definition()],
    )

    assert call.call_id == "anthropic_call_1"
    assert call.name == "get_tutor_instructions"
    assert call.arguments == {"mode": "direct"}
    assert call.provider == "anthropic"
    assert call.validation_error is None


def test_anthropic_tool_result_normalizes_to_internal_shape():
    result = normalize_anthropic_tool_result(
        {"type": "tool_result", "tool_use_id": "anthropic_call_1", "content": "hidden"},
        name="get_tutor_instructions",
        public_preview={"status": "received", "mode": "direct"},
    )

    assert result.call_id == "anthropic_call_1"
    assert result.name == "get_tutor_instructions"
    assert result.content == "hidden"
    assert result.public_preview == {"status": "received", "mode": "direct"}


def test_anthropic_stream_accumulates_incremental_tool_input_json():
    state = AnthropicStreamState()
    tool = tutor_tool_definition()

    start = type(
        "Event",
        (),
        {
            "type": "content_block_start",
            "index": 0,
            "content_block": {
                "type": "tool_use",
                "id": "anthropic_call_1",
                "name": "get_tutor_instructions",
            },
        },
    )()
    delta_1 = type(
        "Event",
        (),
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": '{"mode":"dir'},
        },
    )()
    delta_2 = type(
        "Event",
        (),
        {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "input_json_delta", "partial_json": 'ect"}'},
        },
    )()
    stop = type("Event", (), {"type": "content_block_stop", "index": 0})()

    assert normalize_anthropic_stream_event(start, [tool], state) is None
    assert normalize_anthropic_stream_event(delta_1, [tool], state) is None
    assert normalize_anthropic_stream_event(delta_2, [tool], state) is None
    event = normalize_anthropic_stream_event(stop, [tool], state)

    assert event is not None
    assert event.kind == "tool_call"
    assert event.tool_call is not None
    assert event.tool_call.arguments == {"mode": "direct"}
    assert event.tool_call.validation_error is None


def test_invalid_tool_arguments_fail_safely_without_raw_payload_leakage():
    call = normalize_openai_chat_tool_call(
        {
            "id": "bad_call",
            "function": {
                "name": "get_tutor_instructions",
                "arguments": '{"mode":"lecture","secret":"raw provider payload"}',
            },
        },
        [tutor_tool_definition()],
    )

    assert call.validation_error is not None
    assert "lecture" not in call.validation_error
    assert "raw provider payload" not in call.validation_error


@pytest.mark.anyio
async def test_fake_provider_streams_normalized_tool_events():
    tool = tutor_tool_definition()

    class FakeProvider:
        async def stream(self):
            yield NormalizedStreamEvent.thinking_delta("Plan. ")
            yield NormalizedStreamEvent.tool_call_event(
                normalize_openai_chat_tool_call(
                    {
                        "id": "fake_call",
                        "function": {
                            "name": "get_tutor_instructions",
                            "arguments": '{"mode":"direct"}',
                        },
                    },
                    [tool],
                )
            )
            yield NormalizedStreamEvent.tool_result_event(
                NormalizedToolResult(
                    call_id="fake_call",
                    name="get_tutor_instructions",
                    content="hidden instructions",
                    provider="fake",
                    public_preview={"status": "received", "mode": "direct"},
                )
            )
            yield NormalizedStreamEvent.text_delta("Visible answer")
            yield NormalizedStreamEvent.done_event()

    events = [event async for event in FakeProvider().stream()]

    assert [event.kind for event in events] == [
        "thinking",
        "tool_call",
        "tool_result",
        "text",
        "done",
    ]
    assert events[1].tool_call is not None
    assert events[1].tool_call.arguments == {"mode": "direct"}
    assert events[2].tool_result is not None
    assert events[2].tool_result.public_preview == {"status": "received", "mode": "direct"}
    assert events[3].text == "Visible answer"
