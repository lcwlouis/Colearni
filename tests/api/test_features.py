"""Tests for /settings/features endpoint."""

import os

from apps.api.main import create_app
from core.settings import Settings
from fastapi.testclient import TestClient


def test_feature_flags_defaults():
    settings = Settings(_env_file=None)
    app = create_app(settings=settings)
    client = TestClient(app)
    resp = client.get("/settings/features")
    assert resp.status_code == 200
    data = resp.json()
    assert data["socratic_mode_default"] is False
    assert data["include_dev_stats"] is False


def test_feature_flags_custom(monkeypatch):
    monkeypatch.setenv("APP_SOCRATIC_MODE_DEFAULT", "true")
    monkeypatch.setenv("APP_INCLUDE_DEV_STATS", "true")
    settings = Settings(_env_file=None)
    app = create_app(settings=settings)
    client = TestClient(app)
    resp = client.get("/settings/features")
    assert resp.status_code == 200
    data = resp.json()
    assert data["socratic_mode_default"] is True
    assert data["include_dev_stats"] is True
