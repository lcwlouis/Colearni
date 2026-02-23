"""Smoke tests for health endpoint."""

from apps.api.main import app
from fastapi.testclient import TestClient


def test_healthz_returns_ok_payload() -> None:
    """GET /healthz returns a JSON ok payload."""
    client = TestClient(app)
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"status": "ok"}
