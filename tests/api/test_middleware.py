"""Tests for FastAPI middlewares."""

import pytest
from apps.api.main import create_app
from core.observability import set_event_sink
from core.settings import Settings
from fastapi import FastAPI
from fastapi.testclient import TestClient


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
