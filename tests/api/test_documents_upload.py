"""Tests for document upload endpoint behavior."""

from __future__ import annotations

from typing import Any

from adapters.db.dependencies import get_db_session
from apps.api.main import app
from fastapi.testclient import TestClient


def test_upload_raw_text_returns_201_and_passes_payload(monkeypatch: Any) -> None:
    """Raw text upload should call ingestion and return created payload."""
    captured: dict[str, Any] = {}

    def fake_ingest(_db: object, *, request: Any) -> Any:
        captured["request"] = request
        return type(
            "Result",
            (),
            {
                "document_id": 10,
                "workspace_id": request.workspace_id,
                "title": request.title or "untitled",
                "mime_type": "text/plain",
                "content_hash": "abc123",
                "chunk_count": 2,
                "created": True,
            },
        )()

    monkeypatch.setattr("apps.api.routes.documents.ingest_text_document", fake_ingest)

    def override_db() -> Any:
        yield object()

    app.dependency_overrides[get_db_session] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/documents/upload?workspace_id=7&uploaded_by_user_id=3&title=Doc",
            content="hello world",
            headers={"content-type": "text/plain"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["created"] is True
    assert captured["request"].workspace_id == 7
    assert captured["request"].uploaded_by_user_id == 3
    assert captured["request"].title == "Doc"
    assert captured["request"].raw_bytes == b"hello world"


def test_upload_duplicate_returns_200(monkeypatch: Any) -> None:
    """Duplicate uploads should return 200 with created=false."""

    def fake_ingest(_db: object, *, request: Any) -> Any:
        return type(
            "Result",
            (),
            {
                "document_id": 11,
                "workspace_id": request.workspace_id,
                "title": "Existing Doc",
                "mime_type": "text/markdown",
                "content_hash": "def456",
                "chunk_count": 4,
                "created": False,
            },
        )()

    monkeypatch.setattr("apps.api.routes.documents.ingest_text_document", fake_ingest)

    def override_db() -> Any:
        yield object()

    app.dependency_overrides[get_db_session] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/documents/upload?workspace_id=8&uploaded_by_user_id=4",
            content="# Notes",
            headers={"content-type": "text/markdown"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["created"] is False
