"""Unit tests for observability helpers."""

from __future__ import annotations

from core.observability import (
    configure_observability,
    emit_event,
    observation_context,
    set_event_sink,
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
        prompt="sensitive prompt",
        body={"foo": "bar"},
        token_prompt=12,
    )

    assert len(events) == 1
    event = events[0]
    assert event["api_key"] == "[REDACTED]"
    assert event["prompt"] == "[REDACTED]"
    assert event["body"] == "[REDACTED]"
    assert event["token_prompt"] == 12
    set_event_sink(None)
