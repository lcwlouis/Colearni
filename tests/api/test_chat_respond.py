"""Tests for chat response endpoint behavior."""

from __future__ import annotations

from typing import Any

from adapters.db.dependencies import get_db_session
from adapters.db.documents import DocumentRow
from apps.api.main import app
from core.schemas import GroundingMode
from domain.retrieval.hybrid_retriever import HybridRetriever
from domain.retrieval.types import RankedChunk
from domain.retrieval.vector_retriever import PgVectorRetriever
from fastapi.testclient import TestClient


class DummyEmbeddingProvider:
    """Embedding provider double used by chat API tests."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]


def _override_db() -> Any:
    yield object()


def test_chat_respond_uses_default_grounding_mode_when_request_omits_mode(
    monkeypatch: Any,
) -> None:
    """Request mode should default from app settings when not provided."""
    monkeypatch.setattr(
        "domain.chat.respond.build_embedding_provider",
        lambda settings: DummyEmbeddingProvider(),
    )
    monkeypatch.setattr(
        HybridRetriever,
        "retrieve",
        lambda self, query, workspace_id, top_k: [],  # noqa: ARG005
    )
    monkeypatch.setattr(app.state.settings, "default_grounding_mode", GroundingMode.HYBRID)

    app.dependency_overrides[get_db_session] = _override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/chat/respond",
            json={"workspace_id": 7, "query": "what is a tensor"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["grounding_mode"] == "hybrid"
    assert payload["kind"] == "refusal"
    assert payload["refusal_reason"] == "invalid_citations"


def test_chat_respond_request_mode_overrides_default(monkeypatch: Any) -> None:
    """Explicit request mode should override settings default."""
    monkeypatch.setattr(
        "domain.chat.respond.build_embedding_provider",
        lambda settings: DummyEmbeddingProvider(),
    )
    monkeypatch.setattr(
        HybridRetriever,
        "retrieve",
        lambda self, query, workspace_id, top_k: [],  # noqa: ARG005
    )
    monkeypatch.setattr(app.state.settings, "default_grounding_mode", GroundingMode.HYBRID)

    app.dependency_overrides[get_db_session] = _override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/chat/respond",
            json={
                "workspace_id": 7,
                "query": "what is a tensor",
                "grounding_mode": "strict",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["grounding_mode"] == "strict"
    assert payload["kind"] == "refusal"
    assert payload["refusal_reason"] == "insufficient_evidence"


def test_chat_respond_returns_answer_envelope_with_workspace_citations(
    monkeypatch: Any,
) -> None:
    """Route should return verified answer envelope with citation metadata."""
    ranked_rows = [
        RankedChunk(
            workspace_id=7,
            chunk_id=21,
            document_id=9,
            chunk_index=0,
            text="Linear maps preserve vector addition and scalar multiplication.",
            score=0.93,
            retrieval_method="hybrid",
        )
    ]

    monkeypatch.setattr(
        "domain.chat.respond.build_embedding_provider",
        lambda settings: DummyEmbeddingProvider(),
    )
    monkeypatch.setattr(
        HybridRetriever,
        "retrieve",
        lambda self, query, workspace_id, top_k: ranked_rows,  # noqa: ARG005
    )
    monkeypatch.setattr(
        "domain.chat.respond.get_document_by_id",
        lambda session, workspace_id, document_id: DocumentRow(  # noqa: ARG005
            id=document_id,
            workspace_id=workspace_id,
            title="Linear Algebra Notes",
            source_uri="file://notes.md",
            mime_type="text/markdown",
            content_hash="abc123",
        ),
    )
    monkeypatch.setattr(app.state.settings, "default_grounding_mode", GroundingMode.STRICT)

    app.dependency_overrides[get_db_session] = _override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/chat/respond",
            json={"workspace_id": 7, "query": "describe linear maps"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()

    assert payload["kind"] == "answer"
    assert payload["grounding_mode"] == "strict"
    assert payload["refusal_reason"] is None
    assert payload["evidence"]
    assert payload["citations"]
    assert payload["citations"][0]["label"] == "From your notes"
    assert payload["evidence"][0]["document_id"] == 9


def test_chat_respond_uses_hybrid_retriever_path(monkeypatch: Any) -> None:
    """Chat responder should call HybridRetriever.retrieve (not vector-only directly)."""
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "domain.chat.respond.build_embedding_provider",
        lambda settings: DummyEmbeddingProvider(),
    )

    def fake_hybrid_retrieve(
        self,
        query: str,
        workspace_id: int,
        top_k: int,
    ) -> list[RankedChunk]:
        captured["query"] = query
        captured["workspace_id"] = workspace_id
        captured["top_k"] = top_k
        return []

    monkeypatch.setattr(HybridRetriever, "retrieve", fake_hybrid_retrieve)
    monkeypatch.setattr(
        PgVectorRetriever,
        "retrieve",
        lambda self, query, workspace_id, top_k: (_ for _ in ()).throw(
            AssertionError("vector-only retrieval path should not be called directly")
        ),
    )
    monkeypatch.setattr(app.state.settings, "default_grounding_mode", GroundingMode.HYBRID)

    app.dependency_overrides[get_db_session] = _override_db
    try:
        client = TestClient(app)
        response = client.post(
            "/chat/respond",
            json={"workspace_id": 12, "query": "hybrid path", "top_k": 4},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured == {"query": "hybrid path", "workspace_id": 12, "top_k": 4}
