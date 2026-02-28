"""Unit tests for observability helpers."""

from __future__ import annotations

import threading

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

from core.observability import (
    configure_observability,
    emit_event,
    observation_context,
    record_content_enabled,
    set_event_sink,
    set_llm_span_attributes,
    set_tracer_provider_for_testing,
    start_span,
)
from core.settings import get_settings


class _InMemoryExporter(SpanExporter):
    """Minimal in-memory span exporter for test assertions."""

    def __init__(self):
        self._spans: list = []
        self._lock = threading.Lock()

    def export(self, spans):
        with self._lock:
            self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def get_finished_spans(self):
        with self._lock:
            return list(self._spans)

    def shutdown(self):
        pass


@pytest.fixture()
def otel_exporter():
    """Provide an in-memory OTel exporter for span assertions."""
    exporter = _InMemoryExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    set_tracer_provider_for_testing(provider)

    settings = get_settings().model_copy(
        update={
            "observability_enabled": True,
            "observability_otlp_endpoint": None,
            "observability_service_name": "colearni-test",
        }
    )
    configure_observability(settings)
    yield exporter
    set_tracer_provider_for_testing(None)


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


# ---- OBS-1: Trace foundation tests ----


def test_start_span_sets_ok_status_on_success(otel_exporter) -> None:
    """start_span marks span OK when body completes without error."""
    with start_span("test.success"):
        pass

    spans = otel_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "test.success"
    assert spans[0].status.status_code == trace.StatusCode.OK


def test_start_span_sets_error_status_on_exception(otel_exporter) -> None:
    """start_span marks span ERROR and records exception on failure."""
    with pytest.raises(ValueError, match="boom"):
        with start_span("test.failure"):
            raise ValueError("boom")

    spans = otel_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.status.status_code == trace.StatusCode.ERROR
    assert "boom" in (span.status.description or "")
    # Exception should be recorded as a span event
    event_names = [e.name for e in span.events]
    assert "exception" in event_names


def test_emit_event_attaches_to_active_span(otel_exporter) -> None:
    """emit_event writes a span event on the active span."""
    with start_span("test.parent"):
        emit_event("domain.action", status="ok", component="test")

    spans = otel_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    event_names = [e.name for e in span.events]
    assert "domain.action" in event_names
    # Verify event attributes contain the status
    domain_events = [e for e in span.events if e.name == "domain.action"]
    assert domain_events[0].attributes["status"] == "ok"


def test_emit_event_works_without_active_span(otel_exporter) -> None:
    """emit_event still logs and returns payload when no span is active."""
    events: list[dict[str, object]] = []
    set_event_sink(events)

    result = emit_event("standalone.event", status="info")

    assert result is not None
    assert result["event_name"] == "standalone.event"
    assert len(events) == 1
    set_event_sink(None)


# ---- OBS-3: Prompt identity and content policy tests ----


def test_set_prompt_metadata_on_span(otel_exporter) -> None:
    """set_prompt_metadata attaches prompt.id, prompt.version, prompt.task_type."""
    from dataclasses import dataclass

    from core.observability import set_prompt_metadata

    @dataclass
    class FakeMeta:
        prompt_id: str = "tutor_socratic_v1"
        version: int = 2
        task_type: str = "tutor"

    with start_span("test.prompt") as span:
        set_prompt_metadata(span, FakeMeta(), rendered_length=500)

    spans = otel_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes.get("prompt.id") == "tutor_socratic_v1"
    assert spans[0].attributes.get("prompt.version") == 2
    assert spans[0].attributes.get("prompt.task_type") == "tutor"
    assert spans[0].attributes.get("prompt.rendered_length") == 500


def test_content_preview_truncates_long_text() -> None:
    """content_preview returns a truncated string with length for long text."""
    from core.observability import content_preview

    short = "hello"
    assert content_preview(short) == "hello"

    long_text = "x" * 1000
    preview = content_preview(long_text)
    assert preview is not None
    assert len(preview) < 1000
    assert "len=1000" in preview

    assert content_preview(None) is None


def test_classify_usage_source() -> None:
    """classify_usage_source returns correct labels."""
    from core.observability import classify_usage_source

    assert classify_usage_source({"token_prompt": 10, "token_completion": 5, "token_total": 15}) == "provider_reported"
    assert classify_usage_source({"token_prompt": None, "token_completion": None, "token_total": None}) == "missing"
    assert classify_usage_source({"token_prompt": None, "token_completion": None, "token_total": 5}) == "provider_reported"
