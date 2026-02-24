"""Integration test for text document ingestion into Postgres."""

from __future__ import annotations

import uuid

import pytest
from adapters.db.chunks import count_chunks_for_document, search_chunks_full_text
from core.ingestion import IngestionRequest, ingest_text_document
from core.settings import get_settings
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from tests.db.test_graph_resolver_integration import IntegrationGraphLLM


def _new_session_or_skip() -> Session:
    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        session = Session(bind=engine)
    except SQLAlchemyError as exc:
        engine.dispose()
        pytest.skip(f"Postgres not available for integration test: {exc}")

    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        session.close()
        engine.dispose()
        pytest.skip(f"Postgres not available for integration test: {exc}")

    return session



def test_ingest_text_document_writes_documents_chunks_and_tsv() -> None:
    """Upload path should create document/chunks and populate searchable TSV data."""
    session = _new_session_or_skip()
    unique_key = uuid.uuid4().hex
    try:
        user_id = int(
            session.execute(
                text(
                    """
                    INSERT INTO users (email, display_name)
                    VALUES (:email, :display_name)
                    RETURNING id
                    """
                ),
                {"email": f"ingest-{unique_key}@example.com", "display_name": "Ingest Tester"},
            ).scalar_one()
        )
        workspace_id = int(
            session.execute(
                text(
                    """
                    INSERT INTO workspaces (name, owner_user_id)
                    VALUES (:name, :owner_user_id)
                    RETURNING id
                    """
                ),
                {"name": f"Ingest Workspace {unique_key}", "owner_user_id": user_id},
            ).scalar_one()
        )
        session.commit()

        result = ingest_text_document(
            session,
            request=IngestionRequest(
                workspace_id=workspace_id,
                uploaded_by_user_id=user_id,
                raw_bytes=(
                    b"# Linear Algebra Notes\n\n"
                    b"A vector space contains vectors and operations.\n"
                    b"Linear transformations map vectors between spaces."
                ),
                content_type="text/markdown",
                filename="notes.md",
                title="LA Notes",
                source_uri=None,
            ),
        )

        assert result.created is True
        assert result.chunk_count >= 1
        assert result.workspace_id == workspace_id

        document_count = int(
            session.execute(
                text("SELECT count(*) FROM documents WHERE id = :document_id"),
                {"document_id": result.document_id},
            ).scalar_one()
        )
        assert document_count == 1

        assert (
            count_chunks_for_document(
                session,
                workspace_id=workspace_id,
                document_id=result.document_id,
            )
            == result.chunk_count
        )

        populated_tsv_count = int(
            session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM chunks
                    WHERE document_id = :document_id
                      AND workspace_id = :workspace_id
                      AND tsv <> ''::tsvector
                    """
                ),
                {"document_id": result.document_id, "workspace_id": workspace_id},
            ).scalar_one()
        )
        assert populated_tsv_count == result.chunk_count

        search_results = search_chunks_full_text(
            session,
            workspace_id=workspace_id,
            query="vectors",
        )
        assert search_results
        assert any("vector" in row.text.lower() for row in search_results)
    finally:
        bind = session.get_bind()
        session.close()
        if bind is not None:
            bind.dispose()


def test_ingest_text_document_populates_chunk_embeddings_when_enabled() -> None:
    """Embedding-enabled ingestion should store non-null embeddings for new chunks."""
    session = _new_session_or_skip()
    unique_key = uuid.uuid4().hex
    try:
        user_id = int(
            session.execute(
                text(
                    """
                    INSERT INTO users (email, display_name)
                    VALUES (:email, :display_name)
                    RETURNING id
                    """
                ),
                {"email": f"ingest-emb-{unique_key}@example.com", "display_name": "Embed Tester"},
            ).scalar_one()
        )
        workspace_id = int(
            session.execute(
                text(
                    """
                    INSERT INTO workspaces (name, owner_user_id)
                    VALUES (:name, :owner_user_id)
                    RETURNING id
                    """
                ),
                {"name": f"Embed Workspace {unique_key}", "owner_user_id": user_id},
            ).scalar_one()
        )
        session.commit()

        settings = get_settings().model_copy(
            update={
                "ingest_populate_embeddings": True,
                "embedding_provider": "mock",
            }
        )
        result = ingest_text_document(
            session,
            request=IngestionRequest(
                workspace_id=workspace_id,
                uploaded_by_user_id=user_id,
                raw_bytes=(
                    b"Embedding-enabled ingestion should populate vectors.\n"
                    b"This line helps create sufficient deterministic chunk content."
                ),
                content_type="text/plain",
                filename="embeddings.txt",
                title="Embedding Notes",
                source_uri=None,
            ),
            settings=settings,
        )

        embedded_chunk_count = int(
            session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM chunks
                    WHERE workspace_id = :workspace_id
                      AND document_id = :document_id
                      AND embedding IS NOT NULL
                    """
                ),
                {"workspace_id": workspace_id, "document_id": result.document_id},
            ).scalar_one()
        )

        assert result.created is True
        assert result.chunk_count >= 1
        assert embedded_chunk_count == result.chunk_count
    finally:
        bind = session.get_bind()
        session.close()
        if bind is not None:
            bind.dispose()


@pytest.mark.parametrize("ingest_build_graph", [True, False])
def test_ingest_text_document_graph_wiring_enabled_and_disabled(
    ingest_build_graph: bool,
) -> None:
    """Graph-enabled mode writes artifacts; disabled mode leaves graph tables untouched."""
    session = _new_session_or_skip()
    unique_key = uuid.uuid4().hex
    try:
        user_id = int(
            session.execute(
                text(
                    """
                    INSERT INTO users (email, display_name)
                    VALUES (:email, :display_name)
                    RETURNING id
                    """
                ),
                {"email": f"ingest-graph-{unique_key}@example.com", "display_name": "Graph Tester"},
            ).scalar_one()
        )
        workspace_id = int(
            session.execute(
                text(
                    """
                    INSERT INTO workspaces (name, owner_user_id)
                    VALUES (:name, :owner_user_id)
                    RETURNING id
                    """
                ),
                {"name": f"Graph Workspace {unique_key}", "owner_user_id": user_id},
            ).scalar_one()
        )
        session.commit()

        settings = get_settings().model_copy(
            update={
                "ingest_build_graph": ingest_build_graph,
                "ingest_populate_embeddings": False,
            }
        )
        result = ingest_text_document(
            session,
            request=IngestionRequest(
                workspace_id=workspace_id,
                uploaded_by_user_id=user_id,
                raw_bytes=b"Vector spaces and linear independence are core linear algebra topics.",
                content_type="text/plain",
                filename="graph.txt",
                title="Graph Notes",
                source_uri=None,
            ),
            settings=settings,
            graph_llm_client=IntegrationGraphLLM(),
        )
        params = {"workspace_id": workspace_id, "document_id": result.document_id}
        concepts_raw = int(
            session.execute(
                text(
                    """
                    SELECT count(*) FROM concepts_raw
                    WHERE workspace_id = :workspace_id AND chunk_id IN (
                        SELECT id FROM chunks
                        WHERE workspace_id = :workspace_id AND document_id = :document_id
                    )
                    """
                ),
                params,
            ).scalar_one()
        )
        edges_raw = int(
            session.execute(
                text(
                    """
                    SELECT count(*) FROM edges_raw
                    WHERE workspace_id = :workspace_id AND chunk_id IN (
                        SELECT id FROM chunks
                        WHERE workspace_id = :workspace_id AND document_id = :document_id
                    )
                    """
                ),
                params,
            ).scalar_one()
        )
        concepts_canon = int(
            session.execute(
                text("SELECT count(*) FROM concepts_canon WHERE workspace_id = :workspace_id"),
                {"workspace_id": workspace_id},
            ).scalar_one()
        )
        edges_canon = int(
            session.execute(
                text("SELECT count(*) FROM edges_canon WHERE workspace_id = :workspace_id"),
                {"workspace_id": workspace_id},
            ).scalar_one()
        )
        alias_map = int(
            session.execute(
                text("SELECT count(*) FROM concept_merge_map WHERE workspace_id = :workspace_id"),
                {"workspace_id": workspace_id},
            ).scalar_one()
        )
        provenance = int(
            session.execute(
                text("SELECT count(*) FROM provenance WHERE workspace_id = :workspace_id"),
                {"workspace_id": workspace_id},
            ).scalar_one()
        )

        assert result.created is True
        if ingest_build_graph:
            assert concepts_raw >= 2
            assert edges_raw >= 1
            assert concepts_canon >= 2
            assert edges_canon >= 1
            assert alias_map >= 2
            assert provenance >= 3
        else:
            assert concepts_raw == 0
            assert edges_raw == 0
            assert concepts_canon == 0
            assert edges_canon == 0
            assert alias_map == 0
            assert provenance == 0
    finally:
        bind = session.get_bind()
        session.close()
        if bind is not None:
            bind.dispose()
