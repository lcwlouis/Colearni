"""Tests for document upload endpoint behavior."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from adapters.db.dependencies import get_db_session
from apps.api.main import app, create_app
from core.ingestion import (
    IngestionEmbeddingUnavailableError,
    IngestionGraphProviderError,
    IngestionGraphUnavailableError,
    IngestionValidationError,
)
from core.settings import get_settings
from fastapi.testclient import TestClient


def _created_result(*, request: Any) -> Any:
    return SimpleNamespace(
        document_id=17,
        workspace_id=request.workspace_id,
        title=request.title or "untitled",
        mime_type="text/plain",
        content_hash="hash",
        chunk_count=1,
        created=True,
    )


def _upload_once(app_instance: Any) -> Any:
    def override_db() -> Any:
        yield object()

    app_instance.dependency_overrides[get_db_session] = override_db
    try:
        client = TestClient(app_instance)
        return client.post(
            "/documents/upload?workspace_id=1&uploaded_by_user_id=1",
            content="hello",
            headers={"content-type": "text/plain"},
        )
    finally:
        app_instance.dependency_overrides.clear()


def test_upload_raw_text_returns_201_and_passes_payload(monkeypatch: Any) -> None:
    """Raw text upload should call ingestion and return created payload."""
    captured: dict[str, Any] = {}

    def fake_ingest(
        _db: object,
        *,
        request: Any,
        settings: Any = None,
        graph_llm_client: Any = None,
        graph_embedding_provider: Any = None,
    ) -> Any:
        captured["request"] = request
        captured["settings"] = settings
        captured["graph_llm_client"] = graph_llm_client
        captured["graph_embedding_provider"] = graph_embedding_provider
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
    settings = get_settings().model_copy(update={"ingest_build_graph": False})
    graph_llm_client = object()
    graph_embedding_provider = object()
    monkeypatch.setattr(app.state, "settings", settings, raising=False)
    monkeypatch.setattr(app.state, "graph_llm_client", graph_llm_client, raising=False)
    monkeypatch.setattr(
        app.state,
        "graph_embedding_provider",
        graph_embedding_provider,
        raising=False,
    )

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
    assert captured["settings"] is settings
    assert captured["graph_llm_client"] is graph_llm_client
    assert captured["graph_embedding_provider"] is graph_embedding_provider


def test_upload_duplicate_returns_200(monkeypatch: Any) -> None:
    """Duplicate uploads should return 200 with created=false."""

    def fake_ingest(
        _db: object,
        *,
        request: Any,
        settings: Any = None,  # noqa: ARG001
        graph_llm_client: Any = None,  # noqa: ARG001
        graph_embedding_provider: Any = None,  # noqa: ARG001
    ) -> Any:
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


def test_upload_returns_503_when_embedding_provider_is_unavailable(monkeypatch: Any) -> None:
    def fake_ingest(
        _db: object,
        *,
        request: Any,
        settings: Any = None,  # noqa: ARG001
        graph_llm_client: Any = None,  # noqa: ARG001
        graph_embedding_provider: Any = None,  # noqa: ARG001
    ) -> Any:  # noqa: ARG001
        raise IngestionEmbeddingUnavailableError("Embedding provider is unavailable.")

    monkeypatch.setattr("apps.api.routes.documents.ingest_text_document", fake_ingest)

    def override_db() -> Any:
        yield object()

    app.dependency_overrides[get_db_session] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/documents/upload?workspace_id=9&uploaded_by_user_id=4",
            content="embedding test",
            headers={"content-type": "text/plain"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Embedding provider is unavailable."


def test_upload_returns_503_when_graph_builder_is_unavailable(monkeypatch: Any) -> None:
    def fake_ingest(
        _db: object,
        *,
        request: Any,
        settings: Any = None,  # noqa: ARG001
        graph_llm_client: Any = None,  # noqa: ARG001
        graph_embedding_provider: Any = None,  # noqa: ARG001
    ) -> Any:  # noqa: ARG001
        raise IngestionGraphUnavailableError("Graph builder is unavailable.")

    monkeypatch.setattr("apps.api.routes.documents.ingest_text_document", fake_ingest)

    def override_db() -> Any:
        yield object()

    app.dependency_overrides[get_db_session] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/documents/upload?workspace_id=9&uploaded_by_user_id=4",
            content="graph test",
            headers={"content-type": "text/plain"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Graph builder is unavailable."


def test_upload_returns_422_for_non_extractable_pdf(monkeypatch: Any) -> None:
    def fake_ingest(
        _db: object,
        *,
        request: Any,
        settings: Any = None,  # noqa: ARG001
        graph_llm_client: Any = None,  # noqa: ARG001
        graph_embedding_provider: Any = None,  # noqa: ARG001
    ) -> Any:  # noqa: ARG001
        raise IngestionValidationError(
            "PDF has no extractable text layer. Only text-extractable PDFs are supported."
        )

    monkeypatch.setattr("apps.api.routes.documents.ingest_text_document", fake_ingest)

    def override_db() -> Any:
        yield object()

    app.dependency_overrides[get_db_session] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/documents/upload?workspace_id=9&uploaded_by_user_id=4",
            content=b"%PDF-1.4",
            headers={"content-type": "application/pdf"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert (
        response.json()["detail"]
        == "PDF has no extractable text layer. Only text-extractable PDFs are supported."
    )


def test_create_app_graph_enabled_builds_client_and_upload_passes_it(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}
    graph_llm_client = object()
    settings = get_settings().model_copy(update={"ingest_build_graph": True})
    monkeypatch.setattr(
        "apps.api.main.build_graph_llm_client",
        lambda settings: graph_llm_client,  # noqa: ARG005
    )
    app_instance = create_app(settings=settings)

    def fake_ingest(
        _db: object,
        *,
        request: Any,
        settings: Any = None,
        graph_llm_client: Any = None,
        graph_embedding_provider: Any = None,  # noqa: ARG001
    ) -> Any:
        captured["settings"] = settings
        captured["graph_llm_client"] = graph_llm_client
        return _created_result(request=request)

    monkeypatch.setattr("apps.api.routes.documents.ingest_text_document", fake_ingest)
    response = _upload_once(app_instance)

    assert response.status_code == 201
    assert app_instance.state.graph_llm_client is graph_llm_client
    assert captured["settings"] is settings
    assert captured["graph_llm_client"] is graph_llm_client


def test_create_app_graph_disabled_skips_client_build(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}
    settings = get_settings().model_copy(update={"ingest_build_graph": False})
    monkeypatch.setattr(
        "apps.api.main.build_graph_llm_client",
        lambda settings: (_ for _ in ()).throw(  # noqa: ARG005
            AssertionError("graph client factory should not run when graph ingestion is disabled")
        ),
    )
    app_instance = create_app(settings=settings)

    def fake_ingest(
        _db: object,
        *,
        request: Any,
        settings: Any = None,
        graph_llm_client: Any = None,
        graph_embedding_provider: Any = None,  # noqa: ARG001
    ) -> Any:
        captured["settings"] = settings
        captured["graph_llm_client"] = graph_llm_client
        return _created_result(request=request)

    monkeypatch.setattr("apps.api.routes.documents.ingest_text_document", fake_ingest)
    response = _upload_once(app_instance)

    assert response.status_code == 201
    assert app_instance.state.graph_llm_client is None
    assert captured["settings"] is settings
    assert captured["graph_llm_client"] is None


def test_create_app_graph_enabled_propagates_client_config_errors(monkeypatch: Any) -> None:
    settings = get_settings().model_copy(update={"ingest_build_graph": True})
    monkeypatch.setattr(
        "apps.api.main.build_graph_llm_client",
        lambda settings: (_ for _ in ()).throw(ValueError("bad graph config")),  # noqa: ARG005
    )

    with pytest.raises(ValueError, match="bad graph config"):
        create_app(settings=settings)


def test_upload_returns_502_when_graph_provider_fails(monkeypatch: Any) -> None:
    def fake_ingest(
        _db: object,
        *,
        request: Any,
        settings: Any = None,  # noqa: ARG001
        graph_llm_client: Any = None,  # noqa: ARG001
        graph_embedding_provider: Any = None,  # noqa: ARG001
    ) -> Any:  # noqa: ARG001
        raise IngestionGraphProviderError(
            "Graph extraction failed: Graph LLM request failed: status 400"
        )

    monkeypatch.setattr("apps.api.routes.documents.ingest_text_document", fake_ingest)

    def override_db() -> Any:
        yield object()

    app.dependency_overrides[get_db_session] = override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/documents/upload?workspace_id=9&uploaded_by_user_id=4",
            content="graph provider test",
            headers={"content-type": "text/plain"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 502
    assert "Graph extraction failed" in response.json()["detail"]
