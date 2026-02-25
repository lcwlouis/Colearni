"""Minimal observability helpers for structured events and OpenTelemetry spans."""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import threading
from collections.abc import Mapping
from typing import Any

from opentelemetry import trace

_LOGGER = logging.getLogger("colearni.observability")
_LOCK = threading.Lock()
_OBSERVABILITY_ENABLED = False
_CONFIG_SIGNATURE: tuple[str, str | None] | None = None
_EVENT_SINK: list[dict[str, Any]] | None = None

_OBSERVATION_CONTEXT: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "colearni_observation_context",
    default={},
)

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
_SAFE_TOKEN_KEYS = {"token_prompt", "token_completion", "token_total"}
_SENSITIVE_MARKERS = (
    "api_key",
    "authorization",
    "password",
    "secret",
    "token",
    "prompt",
    "content",
    "payload",
    "body",
)
_MAX_VALUE_CHARS = 512


def configure_observability(settings: Any) -> None:
    """Initialize observability wiring from settings in an idempotent way."""
    global _OBSERVABILITY_ENABLED, _CONFIG_SIGNATURE

    enabled = bool(getattr(settings, "observability_enabled", False))
    _OBSERVABILITY_ENABLED = enabled
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
    """Start a trace span when observability is enabled."""
    if not _OBSERVABILITY_ENABLED:
        yield None
        return

    tracer = trace.get_tracer("colearni.observability")
    combined = dict(get_observation_context())
    combined.update(attributes)
    with tracer.start_as_current_span(name) as span:
        _set_span_attributes(span, combined)
        yield span


def get_observation_context() -> dict[str, Any]:
    """Return a copy of the active observation context values."""
    return dict(_OBSERVATION_CONTEXT.get())


def emit_event(event_name: str, *, status: str, **fields: Any) -> dict[str, Any] | None:
    """Emit a structured observability event with null-safe common fields."""
    if not _OBSERVABILITY_ENABLED:
        return None

    payload: dict[str, Any] = {key: None for key in _COMMON_EVENT_KEYS}
    payload.update(get_observation_context())
    payload.update(fields)
    payload["event_name"] = event_name
    payload["status"] = status
    sanitized = _sanitize_mapping(payload)

    _LOGGER.info("observability_event %s", json.dumps(sanitized, sort_keys=True))
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


def _build_otlp_http_exporter(endpoint: str | None):
    if endpoint is None:
        return None
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
    if lowered not in _SAFE_TOKEN_KEYS and any(marker in lowered for marker in _SENSITIVE_MARKERS):
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
    "configure_observability",
    "emit_event",
    "extract_token_usage",
    "get_observation_context",
    "observation_context",
    "set_event_sink",
    "start_span",
]
