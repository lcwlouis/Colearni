"""Unit tests for LLM observability emission."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from adapters.llm.providers import LiteLLMGraphLLMClient
from core.observability import configure_observability, observation_context, set_event_sink
from core.settings import get_settings


def _make_sdk_response(content: str, usage: dict[str, int] | None = None) -> Any:
    """Build a litellm-style ModelResponse mock that supports .model_dump()."""
    base: dict[str, Any] = {
        "choices": [{"message": {"content": content}}],
    }
    if usage:
        base["usage"] = usage
    return SimpleNamespace(model_dump=lambda: base)


def _configure_observability() -> None:
    configure_observability(
        get_settings().model_copy(
            update={
                "observability_enabled": True,
                "observability_otlp_endpoint": None,
                "observability_service_name": "colearni-test",
                "observability_record_content": True,
            }
        )
    )


def test_llm_call_emits_provider_model_operation_and_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[dict[str, Any]] = []
    set_event_sink(events)
    _configure_observability()
    monkeypatch.setattr(
        "litellm.completion",
        lambda **kwargs: _make_sdk_response(
            "ok",
            {"prompt_tokens": 11, "completion_tokens": 5, "total_tokens": 16},
        ),
    )
    client = LiteLLMGraphLLMClient(
        model="gpt-4o-mini",
        timeout_seconds=5.0,
        base_url="http://localhost:4000/v1",
    )

    with observation_context(operation="chat.respond", workspace_id=7):
        text = client.generate_tutor_text(prompt="hello")

    assert text == "ok"
    assert len(events) == 1
    event = events[0]
    assert event["event_name"] == "llm.call"
    assert event["status"] == "success"
    assert event["provider"] == "litellm"
    assert event["model"] == "gpt-4o-mini"
    assert event["operation"] == "chat.respond"
    assert event["workspace_id"] == 7
    assert event["token_prompt"] == 11
    assert event["token_completion"] == 5
    assert event["token_total"] == 16
    set_event_sink(None)


def test_llm_call_emits_null_safe_token_fields_when_missing_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[dict[str, Any]] = []
    set_event_sink(events)
    _configure_observability()
    monkeypatch.setattr(
        "litellm.completion",
        lambda **kwargs: _make_sdk_response("ok"),
    )
    client = LiteLLMGraphLLMClient(
        model="gpt-4o-mini",
        timeout_seconds=5.0,
        base_url="http://localhost:4000/v1",
    )

    with observation_context(operation="practice.quiz.generate", workspace_id=9):
        _ = client.generate_tutor_text(prompt="hello")

    assert len(events) == 1
    event = events[0]
    assert event["event_name"] == "llm.call"
    assert event["status"] == "success"
    assert event["token_prompt"] is None
    assert event["token_completion"] is None
    assert event["token_total"] is None
    set_event_sink(None)


def test_llm_call_failure_emits_error_without_sensitive_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[dict[str, Any]] = []
    set_event_sink(events)
    _configure_observability()

    def _raise(**kwargs: Any) -> None:  # noqa: ARG001
        raise ConnectionError("boom")

    monkeypatch.setattr("litellm.completion", _raise)
    client = LiteLLMGraphLLMClient(
        model="gpt-4o-mini",
        timeout_seconds=5.0,
        base_url="http://localhost:4000/v1",
    )

    with observation_context(operation="grading.level_up.submit", workspace_id=11):
        with pytest.raises(RuntimeError, match="Graph LLM request failed"):
            client.generate_tutor_text(prompt="do not log this prompt")

    assert len(events) == 1
    event = events[0]
    assert event["event_name"] == "llm.call"
    assert event["status"] == "failure"
    assert event["error_type"] == "ConnectionError"
    set_event_sink(None)


def test_llm_call_uses_case_specific_temperatures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict[str, Any]] = []

    def _capture(**kwargs: Any) -> Any:
        captured.append(kwargs)
        if "response_format" in kwargs:
            return _make_sdk_response('{"concepts": [], "edges": []}')
        return _make_sdk_response("ok")

    monkeypatch.setattr("litellm.completion", _capture)
    client = LiteLLMGraphLLMClient(
        model="gpt-4o-mini",
        timeout_seconds=5.0,
        base_url="http://localhost:4000/v1",
        json_temperature=0.1,
        tutor_temperature=0.7,
    )

    _ = client.extract_raw_graph(chunk_text="Newton's second law")
    _ = client.generate_tutor_text(prompt="Explain this concept")

    assert captured[0]["temperature"] == pytest.approx(0.1)
    assert captured[1]["temperature"] == pytest.approx(0.7)
