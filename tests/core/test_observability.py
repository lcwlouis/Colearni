"""Unit tests for observability helpers."""

from __future__ import annotations

from core.observability import (
    configure_observability,
    emit_event,
    observation_context,
    record_content_enabled,
    set_event_sink,
    set_llm_span_attributes,
)
from core.settings import get_settings


def test_emit_event_is_noop_when_observability_is_disabled() -> None:
    events: list[dict[str, object]] = []
    set_event_sink(events)
    settings = get_settings().model_copy(
        update={
            "observability_enabled": False,
            "observability_otlp_endpoint": None,
            "observability_service_name": "colearni-test",
        }
    )
    configure_observability(settings)

    emitted = emit_event("test.disabled", status="info", workspace_id=1)

    assert emitted is None
    assert events == []
    set_event_sink(None)


def test_emit_event_uses_context_fields() -> None:
    events: list[dict[str, object]] = []
    set_event_sink(events)
    settings = get_settings().model_copy(
        update={
            "observability_enabled": True,
            "observability_otlp_endpoint": None,
            "observability_service_name": "colearni-test",
        }
    )
    configure_observability(settings)

    with observation_context(
        component="unit",
        operation="unit.test",
        workspace_id=42,
        run_id="run-42",
    ):
        emit_event("unit.event", status="success", provider="openai", model="gpt-test")

    assert len(events) == 1
    event = events[0]
    assert event["event_name"] == "unit.event"
    assert event["status"] == "success"
    assert event["workspace_id"] == 42
    assert event["run_id"] == "run-42"
    assert event["operation"] == "unit.test"
    assert event["provider"] == "openai"
    assert event["model"] == "gpt-test"
    set_event_sink(None)


def test_emit_event_redacts_sensitive_fields() -> None:
    events: list[dict[str, object]] = []
    set_event_sink(events)
    settings = get_settings().model_copy(
        update={
            "observability_enabled": True,
            "observability_otlp_endpoint": None,
            "observability_service_name": "colearni-test",
        }
    )
    configure_observability(settings)

    emit_event(
        "unit.redaction",
        status="success",
        api_key="secret",
        authorization="Bearer xxx",
        token_prompt=12,
    )

    assert len(events) == 1
    event = events[0]
    assert event["api_key"] == "[REDACTED]"
    assert event["authorization"] == "[REDACTED]"
    # token_prompt is in _SAFE_KEYS, must not be redacted
    assert event["token_prompt"] == 12
    set_event_sink(None)


def test_prompt_and_content_are_not_redacted() -> None:
    """prompt/content/payload/body are no longer in the blocklist."""
    events: list[dict[str, object]] = []
    set_event_sink(events)
    settings = get_settings().model_copy(
        update={
            "observability_enabled": True,
            "observability_otlp_endpoint": None,
            "observability_service_name": "colearni-test",
        }
    )
    configure_observability(settings)

    emit_event(
        "unit.content",
        status="success",
        prompt="visible prompt",
        content="visible content",
    )

    assert len(events) == 1
    event = events[0]
    assert event["prompt"] == "visible prompt"
    assert event["content"] == "visible content"
    set_event_sink(None)


def test_record_content_enabled_follows_settings() -> None:
    settings_on = get_settings().model_copy(
        update={
            "observability_enabled": True,
            "observability_record_content": True,
            "observability_otlp_endpoint": None,
            "observability_service_name": "colearni-test",
        }
    )
    configure_observability(settings_on)
    assert record_content_enabled() is True

    settings_off = get_settings().model_copy(
        update={
            "observability_enabled": True,
            "observability_record_content": False,
            "observability_otlp_endpoint": None,
            "observability_service_name": "colearni-test",
        }
    )
    configure_observability(settings_off)
    assert record_content_enabled() is False


def test_set_llm_span_attributes_on_none_span() -> None:
    """set_llm_span_attributes should not raise when span is None."""
    set_llm_span_attributes(
        None,
        model="gpt-4",
        messages=[{"role": "user", "content": "hello"}],
        response_message="hi",
        token_usage={"token_prompt": 5, "token_completion": 3, "token_total": 8},
    )
