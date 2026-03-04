"""Unit tests for auth-related routes and dependencies."""

from __future__ import annotations

import pytest
from fastapi import status
from fastapi.testclient import TestClient


class TestAuthRouteContract:
    """Test that the auth route contract matches API.md spec (without DB)."""

    def test_magic_link_requires_email(self) -> None:
        """POST /auth/magic-link needs a valid email body."""
        from apps.api.main import create_app
        from core.settings import Settings

        settings = Settings(database_url="postgresql+psycopg://x:x@localhost:5432/x")
        app = create_app(settings=settings)
        client = TestClient(app, raise_server_exceptions=False)
        # Empty body → 422
        res = client.post("/auth/magic-link", json={})
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_verify_requires_token(self) -> None:
        """POST /auth/verify needs a token field."""
        from apps.api.main import create_app
        from core.settings import Settings

        settings = Settings(database_url="postgresql+psycopg://x:x@localhost:5432/x")
        app = create_app(settings=settings)
        client = TestClient(app, raise_server_exceptions=False)
        res = client.post("/auth/verify", json={})
        assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_me_requires_auth(self) -> None:
        """GET /auth/me returns 401 without a token."""
        from apps.api.main import create_app
        from core.settings import Settings

        settings = Settings(database_url="postgresql+psycopg://x:x@localhost:5432/x")
        app = create_app(settings=settings)
        client = TestClient(app, raise_server_exceptions=False)
        res = client.get("/auth/me")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
