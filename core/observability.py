"""Observability helpers with OpenInference semantic conventions for Phoenix."""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import threading
from collections.abc import Mapping, Sequence
from typing import Any

from opentelemetry import trace

_LOGGER = logging.getLogger("colearni.observability")
_LOCK = threading.Lock()
_OBSERVABILITY_ENABLED = False
_RECORD_CONTENT = True
_CONFIG_SIGNATURE: tuple[str, str | None] | None = None
_EVENT_SINK: list[dict[str, Any]] | None = None
_TRACER_PROVIDER: Any = None

_OBSERVATION_CONTEXT: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "colearni_observation_context",
    default={},
)

# ---------------------------------------------------------------------------
# OpenInference semantic convention attribute keys
# ---------------------------------------------------------------------------
OPENINFERENCE_SPAN_KIND = "openinference.span.kind"
LLM_MODEL_NAME = "llm.model_name"
LLM_INPUT_MESSAGES = "llm.input_messages"
LLM_OUTPUT_MESSAGES = "llm.output_messages"
LLM_INVOCATION_PARAMETERS = "llm.invocation_parameters"
LLM_TOKEN_COUNT_PROMPT = "llm.token_count.prompt"
LLM_TOKEN_COUNT_COMPLETION = "llm.token_count.completion"
LLM_TOKEN_COUNT_TOTAL = "llm.token_count.total"
INPUT_VALUE = "input.value"
INPUT_MIME_TYPE = "input.mime_type"
OUTPUT_VALUE = "output.value"
OUTPUT_MIME_TYPE = "output.mime_type"
SESSION_ID = "session.id"
USER_ID = "user.id"
RETRIEVAL_DOCUMENTS = "retrieval.documents"
METADATA = "metadata"

# Span kind constants (values recognised by Phoenix)
SPAN_KIND_LLM = "LLM"
SPAN_KIND_CHAIN = "CHAIN"
SPAN_KIND_RETRIEVER = "RETRIEVER"
SPAN_KIND_EMBEDDING = "EMBEDDING"
SPAN_KIND_TOOL = "TOOL"
SPAN_KIND_AGENT = "AGENT"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
_COMMON_EVENT_KEYS = (
    "event_name",
    "status",
    "component",
    "operation",
    "workspace_id",
    "quiz_id",
    "attempt_id",
    "run_id",
    "provider",
    "model",
    "token_prompt",
    "token_completion",
    "token_total",
    "error_type",
)
_SAFE_KEYS = {
    "token_prompt",
    "token_completion",
    "token_total",
    # OpenInference attribute keys that must never be redacted
    LLM_INPUT_MESSAGES,
    LLM_OUTPUT_MESSAGES,
    LLM_INVOCATION_PARAMETERS,
    LLM_TOKEN_COUNT_PROMPT,
    LLM_TOKEN_COUNT_COMPLETION,
    LLM_TOKEN_COUNT_TOTAL,
    LLM_MODEL_NAME,
    INPUT_VALUE,
    OUTPUT_VALUE,
    INPUT_MIME_TYPE,
    OUTPUT_MIME_TYPE,
    OPENINFERENCE_SPAN_KIND,
    SESSION_ID,
    USER_ID,
    RETRIEVAL_DOCUMENTS,
    METADATA,
}
_SENSITIVE_MARKERS = (
    "api_key",
    "authorization",
    "password",
    "secret",
)
_MAX_VALUE_CHARS = 4096


def configure_observability(settings: Any) -> None:
    """Initialize observability wiring from settings in an idempotent way."""
    global _OBSERVABILITY_ENABLED, _CONFIG_SIGNATURE, _RECORD_CONTENT, _TRACER_PROVIDER

    enabled = bool(getattr(settings, "observability_enabled", False))
    _OBSERVABILITY_ENABLED = enabled
    _RECORD_CONTENT = bool(getattr(settings, "observability_record_content", True))
    if not enabled:
        return

    service_name = str(getattr(settings, "observability_service_name", "colearni-backend")).strip()
    if not service_name:
        service_name = "colearni-backend"
    endpoint = _non_empty_or_none(getattr(settings, "observability_otlp_endpoint", None))
    signature = (service_name, endpoint)

    with _LOCK:
        if _CONFIG_SIGNATURE == signature:
            return

        try:
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
        except ImportError:
            _LOGGER.warning(
                "Observability enabled but OpenTelemetry SDK is unavailable; using no-op tracing."
            )
            _CONFIG_SIGNATURE = signature
            return

        tracer_provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        exporter = _build_otlp_http_exporter(endpoint)
        if exporter is not None:
            tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
        _TRACER_PROVIDER = tracer_provider
        try:
            trace.set_tracer_provider(tracer_provider)
        except Exception:
            # Do not fail app startup if another library already configured tracing.
            _LOGGER.debug("OpenTelemetry tracer provider already configured by another component.")
        _CONFIG_SIGNATURE = signature


@contextlib.contextmanager
def observation_context(**fields: Any):
    """Attach correlation and operation metadata to the current execution context."""
    current = _OBSERVATION_CONTEXT.get()
    merged = dict(current)
    for key, value in fields.items():
        if value is None:
            continue
        merged[key] = value
    token = _OBSERVATION_CONTEXT.set(merged)
    try:
        yield
    finally:
        _OBSERVATION_CONTEXT.reset(token)


@contextlib.contextmanager
def start_span(name: str, **attributes: Any):
    """Start a trace span when observability is enabled.

    Sets span status to OK on normal exit, or ERROR with a recorded
    exception on failure.
    """
    if not _OBSERVABILITY_ENABLED:
        yield None
        return

    tracer = (_TRACER_PROVIDER or trace.get_tracer_provider()).get_tracer("colearni.observability")
    combined = dict(get_observation_context())
    combined.update(attributes)
    with tracer.start_as_current_span(name) as span:
        _set_span_attributes(span, combined)
        try:
            yield span
        except Exception as exc:
            span.set_status(trace.StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            raise
        else:
            span.set_status(trace.StatusCode.OK)


def get_observation_context() -> dict[str, Any]:
    """Return a copy of the active observation context values."""
    return dict(_OBSERVATION_CONTEXT.get())


def record_content_enabled() -> bool:
    """Return whether LLM content recording is enabled."""
    return _OBSERVABILITY_ENABLED and _RECORD_CONTENT


def set_llm_span_attributes(
    span: Any,
    *,
    messages: Sequence[Mapping[str, object]] | None = None,
    response_message: str | None = None,
    model: str | None = None,
    invocation_params: Mapping[str, object] | None = None,
    token_usage: Mapping[str, int | None] | None = None,
) -> None:
    """Set OpenInference LLM span attributes on a trace span.

    Respects the ``record_content_enabled()`` toggle for message content.
    """
    if span is None:
        return

    span.set_attribute(OPENINFERENCE_SPAN_KIND, SPAN_KIND_LLM)

    if model:
        span.set_attribute(LLM_MODEL_NAME, model)

    if invocation_params:
        span.set_attribute(
            LLM_INVOCATION_PARAMETERS,
            json.dumps(dict(invocation_params), default=str)[:_MAX_VALUE_CHARS],
        )

    if record_content_enabled():
        if messages is not None:
            span.set_attribute(
                LLM_INPUT_MESSAGES,
                json.dumps(list(messages), default=str)[:_MAX_VALUE_CHARS],
            )
        if response_message is not None:
            span.set_attribute(
                LLM_OUTPUT_MESSAGES,
                json.dumps(
                    [{"role": "assistant", "content": response_message}], default=str
                )[:_MAX_VALUE_CHARS],
            )

    if token_usage:
        if token_usage.get("token_prompt") is not None:
            span.set_attribute(LLM_TOKEN_COUNT_PROMPT, int(token_usage["token_prompt"]))
        if token_usage.get("token_completion") is not None:
            span.set_attribute(LLM_TOKEN_COUNT_COMPLETION, int(token_usage["token_completion"]))
        if token_usage.get("token_total") is not None:
            span.set_attribute(LLM_TOKEN_COUNT_TOTAL, int(token_usage["token_total"]))


def set_span_kind(span: Any, kind: str) -> None:
    """Set the OpenInference span kind on a trace span."""
    if span is not None:
        span.set_attribute(OPENINFERENCE_SPAN_KIND, kind)


def set_input_output(
    span: Any,
    *,
    input_value: str | None = None,
    output_value: str | None = None,
    input_mime_type: str = "text/plain",
    output_mime_type: str = "text/plain",
) -> None:
    """Set input/output values on a trace span, gated by content recording toggle."""
    if span is None:
        return
    if record_content_enabled():
        if input_value is not None:
            span.set_attribute(INPUT_VALUE, input_value[:_MAX_VALUE_CHARS])
            span.set_attribute(INPUT_MIME_TYPE, input_mime_type)
        if output_value is not None:
            span.set_attribute(OUTPUT_VALUE, output_value[:_MAX_VALUE_CHARS])
            span.set_attribute(OUTPUT_MIME_TYPE, output_mime_type)


def emit_event(event_name: str, *, status: str, **fields: Any) -> dict[str, Any] | None:
    """Emit a structured observability event with null-safe common fields.

    In addition to logging, the sanitized payload is attached to the
    current active span (if any) via ``span.add_event`` so that Phoenix
    shows domain events in its Events tab.
    """
    if not _OBSERVABILITY_ENABLED:
        return None

    payload: dict[str, Any] = {key: None for key in _COMMON_EVENT_KEYS}
    payload.update(get_observation_context())
    payload.update(fields)
    payload["event_name"] = event_name
    payload["status"] = status
    sanitized = _sanitize_mapping(payload)

    _LOGGER.info("observability_event %s", json.dumps(sanitized, sort_keys=True))

    # Attach to active OTel span so Phoenix Events tab shows domain events
    active_span = trace.get_current_span()
    if active_span is not None and active_span.is_recording():
        span_attrs = {
            k: v for k, v in sanitized.items() if isinstance(v, (str, bool, int, float))
        }
        active_span.add_event(event_name, attributes=span_attrs)

    if _EVENT_SINK is not None:
        _EVENT_SINK.append(dict(sanitized))
    return sanitized


def extract_token_usage(payload: Mapping[str, object]) -> dict[str, int | None]:
    """Return null-safe token usage metrics from provider responses."""
    usage_payload = payload.get("usage")
    if not isinstance(usage_payload, Mapping):
        return {
            "token_prompt": None,
            "token_completion": None,
            "token_total": None,
        }

    prompt = _coerce_int(usage_payload.get("prompt_tokens"))
    if prompt is None:
        prompt = _coerce_int(usage_payload.get("input_tokens"))
    completion = _coerce_int(usage_payload.get("completion_tokens"))
    if completion is None:
        completion = _coerce_int(usage_payload.get("output_tokens"))
    total = _coerce_int(usage_payload.get("total_tokens"))
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    return {
        "token_prompt": prompt,
        "token_completion": completion,
        "token_total": total,
    }


def set_event_sink(events: list[dict[str, Any]] | None) -> None:
    """Set an in-memory sink for tests to capture emitted events."""
    global _EVENT_SINK
    _EVENT_SINK = events


def set_tracer_provider_for_testing(provider: Any) -> None:
    """Override the tracer provider for test isolation."""
    global _TRACER_PROVIDER
    _TRACER_PROVIDER = provider


def _build_otlp_http_exporter(endpoint: str | None):
    if endpoint is None:
        return None
    if not endpoint.rstrip("/").endswith("/v1/traces"):
        endpoint = endpoint.rstrip("/") + "/v1/traces"
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    except ImportError:
        _LOGGER.warning(
            "Observability endpoint set but OTLP HTTP exporter is unavailable; "
            "spans will not export."
        )
        return None
    return OTLPSpanExporter(endpoint=endpoint)


def _set_span_attributes(span: Any, attributes: Mapping[str, Any]) -> None:
    for key, value in attributes.items():
        normalized = _sanitize_value(key, value)
        if normalized is None:
            continue
        if isinstance(normalized, (str, bool, int, float)):
            span.set_attribute(key, normalized)


def _sanitize_mapping(values: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _sanitize_value(str(key), value) for key, value in values.items()}


def _sanitize_value(key: str, value: Any) -> Any:
    lowered = key.strip().lower()
    if lowered not in _SAFE_KEYS and any(marker in lowered for marker in _SENSITIVE_MARKERS):
        return "[REDACTED]"
    if value is None:
        return None
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:_MAX_VALUE_CHARS]
    if isinstance(value, Mapping):
        payload = _sanitize_mapping(value)
        return _truncate_json(payload)
    if isinstance(value, (list, tuple, set)):
        return _truncate_json([_sanitize_value(key, item) for item in value])
    return str(value)[:_MAX_VALUE_CHARS]


def _truncate_json(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, default=str)
    if len(text) <= _MAX_VALUE_CHARS:
        return text
    return text[: _MAX_VALUE_CHARS - 3] + "..."


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(float(stripped))
        except ValueError:
            return None
    return None


def _non_empty_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


__all__ = [
    "OPENINFERENCE_SPAN_KIND",
    "LLM_MODEL_NAME",
    "LLM_INPUT_MESSAGES",
    "LLM_OUTPUT_MESSAGES",
    "LLM_INVOCATION_PARAMETERS",
    "LLM_TOKEN_COUNT_PROMPT",
    "LLM_TOKEN_COUNT_COMPLETION",
    "LLM_TOKEN_COUNT_TOTAL",
    "INPUT_VALUE",
    "INPUT_MIME_TYPE",
    "OUTPUT_VALUE",
    "OUTPUT_MIME_TYPE",
    "SESSION_ID",
    "USER_ID",
    "SPAN_KIND_LLM",
    "SPAN_KIND_CHAIN",
    "SPAN_KIND_RETRIEVER",
    "SPAN_KIND_EMBEDDING",
    "SPAN_KIND_TOOL",
    "SPAN_KIND_AGENT",
    "configure_observability",
    "emit_event",
    "extract_token_usage",
    "get_observation_context",
    "observation_context",
    "record_content_enabled",
    "set_event_sink",
    "set_input_output",
    "set_llm_span_attributes",
    "set_span_kind",
    "set_tracer_provider_for_testing",
    "start_span",
]
