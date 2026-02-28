"""Tests for FastAPI middlewares."""

import threading

import pytest
from apps.api.main import create_app
from core.observability import set_event_sink, set_tracer_provider_for_testing
from core.settings import Settings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult


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


@pytest.fixture
def otel_exporter():
    """Provide an in-memory OTel exporter for span assertions."""
    exporter = _InMemoryExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    set_tracer_provider_for_testing(provider)
    yield exporter
    set_tracer_provider_for_testing(None)


@pytest.fixture
def app_with_cors() -> FastAPI:
    """Create an app configured with specific CORS origins."""
    settings = Settings(
        APP_CORS_ALLOWED_ORIGINS=["https://allowed.example.com"],
        APP_CORS_ALLOWED_METHODS=["*"],
        APP_OBSERVABILITY_ENABLED=True,
    )
    app = create_app(settings=settings)

    @app.get("/_test_emit")
    def test_emit():
        from core.observability import emit_event
        emit_event("test_event", status="ok")
        return {"status": "ok"}

    return app


@pytest.fixture
def client(app_with_cors: FastAPI) -> TestClient:
    """Return a TestClient for the app."""
    return TestClient(app_with_cors)


def test_cors_allowed_origin(client: TestClient) -> None:
    """Test that a configured origin is allowed."""
    response = client.options(
        "/healthz",
        headers={
            "Origin": "https://allowed.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://allowed.example.com"


def test_cors_blocked_origin(client: TestClient) -> None:
    """Test that an unconfigured origin is blocked."""
    response = client.options(
        "/healthz",
        headers={
            "Origin": "https://blocked.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_correlation_id_generated(client: TestClient) -> None:
    """Test that a request receives an auto-generated correlation ID if not provided."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0


def test_correlation_id_propagated(client: TestClient) -> None:
    """Test that an incoming correlation ID is respected and propagated."""
    custom_id = "test-custom-id-123"
    response = client.get("/healthz", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == custom_id


def test_observability_context_includes_request_id(client: TestClient) -> None:
    """Test that the correlation ID is present in the observability event sink."""
    sink: list[dict] = []
    set_event_sink(sink)
    
    custom_id = "obs-test-id-999"
    
    resp = client.get("/_test_emit", headers={"X-Request-ID": custom_id})
    assert resp.status_code == 200
    
    set_event_sink(None)
    
    assert len(sink) == 1
    assert sink[0].get("request_id") == custom_id


# ---- OBS-1: Phoenix scope – no generic HTTP spans ----


def test_no_http_request_span_exported(otel_exporter) -> None:
    """Middleware must NOT create http.request spans – they pollute Phoenix."""
    settings = Settings(
        APP_CORS_ALLOWED_ORIGINS=["*"],
        APP_CORS_ALLOWED_METHODS=["*"],
        APP_OBSERVABILITY_ENABLED=True,
    )
    app = create_app(settings=settings)
    client = TestClient(app)

    response = client.get("/healthz")
    assert response.status_code == 200

    spans = otel_exporter.get_finished_spans()
    http_spans = [s for s in spans if s.name == "http.request"]
    assert http_spans == [], "http.request spans must not be exported to Phoenix"
