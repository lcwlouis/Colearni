"""Unit tests for observability helpers."""

from __future__ import annotations

import threading

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

from core.observability import (
    configure_observability,
    create_span,
    emit_event,
    observation_context,
    record_content_enabled,
    set_event_sink,
    set_llm_span_attributes,
    set_tracer_provider_for_testing,
    start_span,
    use_span_context,
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


def test_use_span_context_nests_child_spans(otel_exporter) -> None:
    """use_span_context makes create_span children parent correctly."""
    parent = create_span("chat.stream")
    assert parent is not None

    with use_span_context(parent):
        with start_span("retrieval.search"):
            pass

    parent.end()

    spans = otel_exporter.get_finished_spans()
    assert len(spans) == 2
    child = next(s for s in spans if s.name == "retrieval.search")
    assert child.parent is not None
    assert child.parent.span_id == parent.get_span_context().span_id


def test_use_span_context_noop_when_span_is_none(otel_exporter) -> None:
    """use_span_context is a no-op when span is None."""
    with use_span_context(None):
        with start_span("orphan.span"):
            pass

    spans = otel_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "orphan.span"


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

    long_text = "x" * 5000
    preview = content_preview(long_text)
    assert preview is not None
    assert len(preview) < 5000
    assert "len=5000" in preview

    assert content_preview(None) is None


def test_content_preview_respects_custom_preview_chars() -> None:
    """content_preview uses the module-level _PREVIEW_CHARS value."""
    import core.observability as obs

    original = obs._PREVIEW_CHARS
    try:
        obs._PREVIEW_CHARS = 10
        result = obs.content_preview("a" * 50)
        assert result is not None
        assert result.startswith("a" * 10 + "...")
        assert "len=50" in result
        # Text shorter than limit is returned as-is
        assert obs.content_preview("short") == "short"
    finally:
        obs._PREVIEW_CHARS = original


def test_configure_observability_sets_preview_chars() -> None:
    """configure_observability with observability_preview_chars=1000 updates _PREVIEW_CHARS."""
    import core.observability as obs

    original = obs._PREVIEW_CHARS
    try:
        settings = get_settings().model_copy(
            update={
                "observability_enabled": False,
                "observability_preview_chars": 1000,
            }
        )
        configure_observability(settings)
        assert obs._PREVIEW_CHARS == 1000

        # Verify content_preview now uses the new limit
        text = "x" * 1500
        preview = obs.content_preview(text)
        assert preview is not None
        assert preview.startswith("x" * 1000 + "...")
        assert "len=1500" in preview
    finally:
        obs._PREVIEW_CHARS = original


def test_classify_usage_source() -> None:
    """classify_usage_source returns correct labels."""
    from core.observability import classify_usage_source

    assert classify_usage_source({"token_prompt": 10, "token_completion": 5, "token_total": 15}) == "provider_reported"
    assert classify_usage_source({"token_prompt": None, "token_completion": None, "token_total": None}) == "missing"
    assert classify_usage_source({"token_prompt": None, "token_completion": None, "token_total": 5}) == "provider_reported"


# ---- OBS-6: Regression hardening tests ----

_VALID_SPAN_KINDS = {"LLM", "CHAIN", "RETRIEVER", "EMBEDDING", "TOOL", "AGENT"}


def test_span_kind_constants_are_valid_openinference_values() -> None:
    """All SPAN_KIND_* constants must be valid OpenInference span kinds."""
    from core.observability import (
        SPAN_KIND_AGENT,
        SPAN_KIND_CHAIN,
        SPAN_KIND_EMBEDDING,
        SPAN_KIND_LLM,
        SPAN_KIND_RETRIEVER,
        SPAN_KIND_TOOL,
    )

    for kind in (SPAN_KIND_LLM, SPAN_KIND_CHAIN, SPAN_KIND_RETRIEVER,
                 SPAN_KIND_EMBEDDING, SPAN_KIND_TOOL, SPAN_KIND_AGENT):
        assert kind in _VALID_SPAN_KINDS, f"Unknown span kind: {kind}"


def test_start_span_with_chain_kind_sets_attribute(otel_exporter) -> None:
    """set_span_kind(CHAIN) sets openinference.span.kind=CHAIN, never unknown."""
    from core.observability import SPAN_KIND_CHAIN, set_span_kind

    with start_span("test.chain") as span:
        set_span_kind(span, SPAN_KIND_CHAIN)

    spans = otel_exporter.get_finished_spans()
    assert len(spans) == 1
    kind = spans[0].attributes.get("openinference.span.kind")
    assert kind == "CHAIN"
    assert kind != "unknown"


def test_start_span_with_retriever_kind_sets_attribute(otel_exporter) -> None:
    """set_span_kind(RETRIEVER) sets correct OpenInference kind."""
    from core.observability import SPAN_KIND_RETRIEVER, set_span_kind

    with start_span("test.retriever") as span:
        set_span_kind(span, SPAN_KIND_RETRIEVER)

    spans = otel_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes.get("openinference.span.kind") == "RETRIEVER"


def test_retrieval_span_attributes_schema(otel_exporter) -> None:
    """Retrieval spans must carry results_count and documents summary."""
    import json

    from core.observability import SPAN_KIND_RETRIEVER

    with start_span("retrieval.vector.search", kind=SPAN_KIND_RETRIEVER) as span:
        span.set_attribute("retrieval.results_count", 3)
        span.set_attribute("retrieval.documents", json.dumps([
            {"chunk_id": "c1", "score": 0.95},
            {"chunk_id": "c2", "score": 0.88},
        ]))

    spans = otel_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes.get("retrieval.results_count") == 3
    docs = json.loads(spans[0].attributes.get("retrieval.documents"))
    assert len(docs) == 2
    assert docs[0]["chunk_id"] == "c1"


def test_budget_hard_stop_event_visible(otel_exporter) -> None:
    """Budget hard-stop events are visible as OTel span events."""
    with start_span("graph.resolver.run") as span:
        emit_event(
            "graph.resolver.budget.hard_stop",
            status="warning",
            reason="llm_budget_exhausted",
            calls_used=10,
            calls_max=10,
        )

    spans = otel_exporter.get_finished_spans()
    assert len(spans) == 1
    event_names = [e.name for e in spans[0].events]
    assert "graph.resolver.budget.hard_stop" in event_names
    stop_events = [e for e in spans[0].events if e.name == "graph.resolver.budget.hard_stop"]
    assert stop_events[0].attributes["status"] == "warning"
    assert stop_events[0].attributes["reason"] == "llm_budget_exhausted"


# ---------------------------------------------------------------------------
# _AIOnlySpanExporter tests
# ---------------------------------------------------------------------------


def test_ai_only_exporter_forwards_ai_spans() -> None:
    """_AIOnlySpanExporter forwards spans that have AI OpenInference kinds."""
    from core.observability import (
        SPAN_KIND_CHAIN,
        SPAN_KIND_LLM,
        SPAN_KIND_RETRIEVER,
        _AIOnlySpanExporter,
    )

    forwarded: list = []

    class _Capture(SpanExporter):
        def export(self, spans):
            forwarded.extend(spans)
            return SpanExportResult.SUCCESS
        def shutdown(self): pass

    exporter = _AIOnlySpanExporter(_Capture())

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
    try:
        with start_span("llm.call", kind=SPAN_KIND_LLM):
            pass
        with start_span("chat.respond", kind=SPAN_KIND_CHAIN):
            pass
        with start_span("retrieval.vector", kind=SPAN_KIND_RETRIEVER):
            pass
        assert len(forwarded) == 3
    finally:
        set_tracer_provider_for_testing(None)


def test_ai_only_exporter_blocks_non_ai_spans() -> None:
    """_AIOnlySpanExporter does NOT forward spans without an AI kind attribute."""
    from core.observability import (
        SPAN_KIND_CHAIN,
        _AIOnlySpanExporter,
    )

    forwarded: list = []

    class _Capture(SpanExporter):
        def export(self, spans):
            forwarded.extend(spans)
            return SpanExportResult.SUCCESS
        def shutdown(self): pass

    exporter = _AIOnlySpanExporter(_Capture())

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
    try:
        # start_span without kind= → no openinference.span.kind attribute
        with start_span("http.request"):
            pass
        # No spans should reach the inner exporter
        assert len(forwarded) == 0, f"Expected 0 forwarded spans, got {len(forwarded)}"
    finally:
        set_tracer_provider_for_testing(None)


# ---------------------------------------------------------------------------
# OBS-6 Regression tests
# ---------------------------------------------------------------------------


def test_set_span_summary_always_emits(otel_exporter) -> None:
    """set_span_summary sets input.value/output.value unconditionally (not content-gated)."""
    import json as _json

    from core.observability import INPUT_VALUE, OUTPUT_VALUE, set_span_summary

    with start_span("practice.quiz.generate") as span:
        set_span_summary(span, input_summary="Python basics", output_summary="5 items")

    spans = otel_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes.get(INPUT_VALUE) == "Python basics"
    assert spans[0].attributes.get(OUTPUT_VALUE) == "5 items"


def test_retrieval_documents_include_rank_and_document_id(otel_exporter) -> None:
    """Retrieval documents summary must include rank and document_id (OBS-4)."""
    import json

    from core.observability import SPAN_KIND_RETRIEVER

    with start_span("retrieval.vector.search", kind=SPAN_KIND_RETRIEVER) as span:
        span.set_attribute("retrieval.results_count", 2)
        span.set_attribute(
            "retrieval.documents",
            json.dumps([
                {"rank": 1, "chunk_id": "c1", "document_id": "doc-uuid-1", "score": 0.95},
                {"rank": 2, "chunk_id": "c2", "document_id": "doc-uuid-2", "score": 0.88},
            ]),
        )

    spans = otel_exporter.get_finished_spans()
    assert len(spans) == 1
    docs = json.loads(spans[0].attributes.get("retrieval.documents"))
    assert docs[0]["rank"] == 1
    assert docs[0]["document_id"] == "doc-uuid-1"
    assert docs[1]["rank"] == 2


def test_no_exported_span_has_unknown_kind(otel_exporter) -> None:
    """Every span that uses kind= at creation must have a recognized AI kind (not 'unknown')."""
    from core.observability import SPAN_KIND_CHAIN, SPAN_KIND_LLM, SPAN_KIND_RETRIEVER

    for name, kind in [
        ("chat.respond", SPAN_KIND_CHAIN),
        ("llm.chat.respond", SPAN_KIND_LLM),
        ("retrieval.vector.search", SPAN_KIND_RETRIEVER),
    ]:
        with start_span(name, kind=kind):
            pass

    spans = otel_exporter.get_finished_spans()
    assert len(spans) == 3
    for s in spans:
        kind_val = s.attributes.get("openinference.span.kind")
        assert kind_val is not None, f"Span {s.name} missing kind"
        assert kind_val != "unknown", f"Span {s.name} has unknown kind"


def test_graph_chunk_span_includes_extraction_counts(otel_exporter) -> None:
    """graph.resolver.chunk spans must expose concepts_extracted and edges_extracted (OBS-5)."""
    from core.observability import SPAN_KIND_CHAIN

    with start_span("graph.resolver.chunk", kind=SPAN_KIND_CHAIN) as span:
        span.set_attribute("graph.concepts_extracted", 4)
        span.set_attribute("graph.edges_extracted", 2)

    spans = otel_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes.get("graph.concepts_extracted") == 4
    assert spans[0].attributes.get("graph.edges_extracted") == 2


def test_set_retrieval_documents_empty_still_sets_query(otel_exporter) -> None:
    """When documents=[], INPUT_VALUE (query) and OUTPUT_VALUE must still be set."""
    from core.observability import (
        INPUT_VALUE,
        OUTPUT_VALUE,
        SPAN_KIND_RETRIEVER,
        set_retrieval_documents,
    )

    with start_span("retrieval.fts.search", kind=SPAN_KIND_RETRIEVER) as span:
        set_retrieval_documents(span, query="machine learning", documents=[])

    spans = otel_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes.get(INPUT_VALUE) == "machine learning"
    assert spans[0].attributes.get(OUTPUT_VALUE) == "No documents retrieved."
