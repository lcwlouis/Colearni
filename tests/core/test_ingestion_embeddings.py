"""Unit tests for ingestion embedding write-path behavior."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from adapters.db.chunks import ChunkRow
from adapters.db.documents import DocumentRow
from core.contracts import EmbeddingProvider, GraphLLMClient
from core.ingestion import (
    IngestionEmbeddingUnavailableError,
    IngestionGraphUnavailableError,
    IngestionRequest,
    ingest_text_document,
)
from core.settings import get_settings
from domain.graph.types import GraphBuildResult


class _FakeResult:
    """Stub query result for _FakeSession.execute()."""

    def scalar_one(self) -> int:
        return 0

    def mappings(self) -> "_FakeResult":
        return self

    def all(self) -> list:
        return []

    def first(self) -> None:
        return None

    def __iter__(self):
        return iter([])


class _FakeSession:
    """Simple session test double that tracks commit calls."""

    def __init__(self) -> None:
        self.commit_calls = 0

    def commit(self) -> None:
        self.commit_calls += 1

    def execute(self, *args: object, **kwargs: object) -> _FakeResult:  # noqa: ARG002
        return _FakeResult()

    def get_bind(self) -> None:
        return None


class _DummyProvider(EmbeddingProvider):
    """Embedding provider test double."""

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float(index)] for index, _ in enumerate(texts)]


class _StubGraphLLM(GraphLLMClient):
    """Graph LLM test double for ingestion wiring checks."""

    def extract_raw_graph(self, *, chunk_text: str) -> dict[str, object]:
        return {"concepts": [], "edges": []}

    def disambiguate(
        self,
        *,
        raw_name: str,
        context_snippet: str | None,
        candidates: Sequence[dict[str, object]],
    ) -> dict[str, object]:
        return {"decision": "CREATE_NEW", "confidence": 1.0}

    def generate_tutor_text(self, *, prompt: str, prompt_meta=None) -> str:
        return "Stub summary for testing."


def _request() -> IngestionRequest:
    return IngestionRequest(
        workspace_id=7,
        uploaded_by_user_id=3,
        raw_bytes=b"alpha beta",
        content_type="text/plain",
        filename="notes.txt",
        title="Notes",
        source_uri=None,
    )


def _patch_new_document_flow(monkeypatch: Any, *, chunks: list[str]) -> None:
    monkeypatch.setattr(
        "domain.ingestion.service.get_document_by_content_hash",
        lambda db, workspace_id, content_hash: None,  # noqa: ARG005
    )
    monkeypatch.setattr("domain.ingestion.service.chunk_text_deterministic", lambda text, **_kw: chunks)  # noqa: ARG005

    def _fake_insert_document(
        db: object,  # noqa: ARG001
        *,
        workspace_id: int,
        uploaded_by_user_id: int,  # noqa: ARG001
        title: str,
        source_uri: str | None,
        mime_type: str,
        content_hash: str,
    ) -> DocumentRow:
        return DocumentRow(
            id=41,
            workspace_id=workspace_id,
            title=title,
            source_uri=source_uri,
            mime_type=mime_type,
            content_hash=content_hash,
        )

    monkeypatch.setattr("domain.ingestion.service.insert_document", _fake_insert_document)
    monkeypatch.setattr(
        "domain.ingestion.service.insert_chunks_bulk",
        lambda db, **kwargs: len(kwargs["chunk_texts"]),  # noqa: ARG005
    )


def test_ingest_populates_chunk_embeddings_when_enabled(monkeypatch: Any) -> None:
    """Enabled ingestion embedding path should write chunks via embedding pipeline."""
    _patch_new_document_flow(monkeypatch, chunks=["first chunk", "second chunk"])
    session = _FakeSession()
    settings = get_settings().model_copy(
        update={
            "ingest_populate_embeddings": True,
            "ingest_build_graph": False,
            "embedding_provider": "mock",
            "embedding_batch_size": 3,
        }
    )
    provider = _DummyProvider()
    captured: dict[str, object] = {}

    def _fake_populate_new_chunk_embeddings(
        *,
        session: object,
        provider: EmbeddingProvider,
        chunks: Sequence[object],
        batch_size: int,
    ) -> list[int]:
        captured["session"] = session
        captured["provider"] = provider
        captured["chunks"] = list(chunks)
        captured["batch_size"] = batch_size
        return [101, 102]

    monkeypatch.setattr(
        "domain.ingestion.service.populate_new_chunk_embeddings",
        _fake_populate_new_chunk_embeddings,
    )
    monkeypatch.setattr(
        "domain.ingestion.service.insert_chunks_bulk",
        lambda *args, **kwargs: (_ for _ in ()).throw(  # noqa: ARG005
            AssertionError("legacy bulk insert path should not run when enabled")
        ),
    )
    monkeypatch.setattr(
        "domain.ingestion.service.build_embedding_provider",
        lambda settings: (_ for _ in ()).throw(  # noqa: ARG005
            AssertionError("provider factory should not be called when provider is injected")
        ),
    )

    result = ingest_text_document(
        session,  # type: ignore[arg-type]
        request=_request(),
        chunk_embedding_provider=provider,
        settings=settings,
    )

    assert result.created is True
    assert result.chunk_count == 2
    assert session.commit_calls == 1
    assert captured["session"] is session
    assert captured["provider"] is provider
    assert captured["batch_size"] == 3
    captured_chunks = captured["chunks"]
    assert captured_chunks is not None
    assert [chunk.chunk_index for chunk in captured_chunks] == [0, 1]
    assert [chunk.text for chunk in captured_chunks] == ["first chunk", "second chunk"]


def test_ingest_uses_legacy_chunk_bulk_insert_when_embeddings_disabled(
    monkeypatch: Any,
) -> None:
    """Disabled embedding mode should preserve existing bulk chunk insert path."""
    _patch_new_document_flow(monkeypatch, chunks=["first", "second"])
    session = _FakeSession()
    settings = get_settings().model_copy(update={"ingest_populate_embeddings": False, "ingest_build_graph": False})
    captured: dict[str, object] = {}

    def _fake_insert_chunks_bulk(
        db: object,
        *,
        workspace_id: int,
        document_id: int,
        chunk_texts: list[str],
    ) -> int:
        captured["db"] = db
        captured["workspace_id"] = workspace_id
        captured["document_id"] = document_id
        captured["chunk_texts"] = list(chunk_texts)
        return len(chunk_texts)

    monkeypatch.setattr("domain.ingestion.service.insert_chunks_bulk", _fake_insert_chunks_bulk)
    monkeypatch.setattr(
        "domain.ingestion.service.populate_new_chunk_embeddings",
        lambda *args, **kwargs: (_ for _ in ()).throw(  # noqa: ARG005
            AssertionError("embedding path should not run when disabled")
        ),
    )

    result = ingest_text_document(
        session,  # type: ignore[arg-type]
        request=_request(),
        settings=settings,
    )

    assert result.created is True
    assert result.chunk_count == 2
    assert session.commit_calls == 1
    assert captured == {
        "db": session,
        "workspace_id": 7,
        "document_id": 41,
        "chunk_texts": ["first", "second"],
    }


def test_ingest_raises_when_embeddings_enabled_and_provider_is_unavailable(
    monkeypatch: Any,
) -> None:
    """Embedding-enabled ingestion should fail clearly when provider is unavailable."""
    _patch_new_document_flow(monkeypatch, chunks=["chunk"])
    session = _FakeSession()
    settings = get_settings().model_copy(
        update={
            "ingest_populate_embeddings": True,
            "ingest_build_graph": False,
            "embedding_provider": "openai",
            "openai_api_key": None,
        }
    )

    monkeypatch.setattr(
        "domain.ingestion.service.build_embedding_provider",
        lambda settings: (_ for _ in ()).throw(  # noqa: ARG005
            ValueError("missing openai api key")
        ),
    )
    monkeypatch.setattr(
        "domain.ingestion.service.insert_chunks_bulk",
        lambda *args, **kwargs: (_ for _ in ()).throw(  # noqa: ARG005
            AssertionError("legacy insert path should not run")
        ),
    )

    with pytest.raises(
        IngestionEmbeddingUnavailableError,
        match="APP_INGEST_POPULATE_EMBEDDINGS=true",
    ):
        ingest_text_document(
            session,  # type: ignore[arg-type]
            request=_request(),
            settings=settings,
        )

    assert session.commit_calls == 0


def test_ingest_graph_enabled_calls_builder_with_settings_and_provider_fallback(
    monkeypatch: Any,
) -> None:
    """Graph-enabled ingestion should pass active settings and fallback provider into builder."""
    _patch_new_document_flow(monkeypatch, chunks=["chunk"])
    session = _FakeSession()
    settings = get_settings().model_copy(
        update={"ingest_build_graph": True, "resolver_max_llm_calls_per_chunk": 9}
    )
    chunk_provider = _DummyProvider()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "domain.ingestion.service.list_chunks_for_document",
        lambda db, **kwargs: [  # noqa: ARG005
            ChunkRow(id=501, document_id=41, chunk_index=0, text="chunk")
        ],
    )

    def _fake_graph_build(session: object, **kwargs: object) -> GraphBuildResult:  # noqa: ARG001
        captured.update(kwargs)
        return GraphBuildResult(
            raw_concepts_written=0,
            raw_edges_written=0,
            canonical_created=0,
            canonical_merged=0,
            canonical_edges_upserted=0,
            llm_disambiguations=0,
        )

    monkeypatch.setattr("domain.ingestion.service.build_graph_for_chunks", _fake_graph_build)

    result = ingest_text_document(
        session,  # type: ignore[arg-type]
        request=_request(),
        chunk_embedding_provider=chunk_provider,
        graph_llm_client=_StubGraphLLM(),
        settings=settings,
    )

    assert result.created is True
    assert captured["embedding_provider"] is chunk_provider
    assert captured["settings"] is settings
    assert captured["settings"].resolver_max_llm_calls_per_chunk == 9


def test_ingest_graph_enabled_without_client_raises(monkeypatch: Any) -> None:
    """Graph-enabled ingestion should fail fast when graph client is not configured."""
    _patch_new_document_flow(monkeypatch, chunks=["chunk"])
    session = _FakeSession()
    settings = get_settings().model_copy(update={"ingest_build_graph": True})

    with pytest.raises(IngestionGraphUnavailableError, match="APP_INGEST_BUILD_GRAPH=true"):
        ingest_text_document(
            session,  # type: ignore[arg-type]
            request=_request(),
            settings=settings,
        )

    assert session.commit_calls == 0


def test_ingest_graph_disabled_skips_builder_even_when_client_is_present(
    monkeypatch: Any,
) -> None:
    """Graph-disabled ingestion should preserve current behavior and skip graph pipeline."""
    _patch_new_document_flow(monkeypatch, chunks=["chunk"])
    session = _FakeSession()
    settings = get_settings().model_copy(update={"ingest_build_graph": False, "ingest_populate_embeddings": False})
    monkeypatch.setattr(
        "domain.ingestion.service.build_graph_for_chunks",
        lambda *args, **kwargs: (_ for _ in ()).throw(  # noqa: ARG005
            AssertionError("graph builder should not run when disabled")
        ),
    )

    result = ingest_text_document(
        session,  # type: ignore[arg-type]
        request=_request(),
        graph_llm_client=_StubGraphLLM(),
        settings=settings,
    )

    assert result.created is True
    assert session.commit_calls == 1
