"""Integration tests for pgvector chunk similarity retrieval."""

from __future__ import annotations

from uuid import uuid4

import pytest
from adapters.db.chunks_repository import (
    ChunkInsertRow,
    insert_chunks_with_embeddings,
    vector_top_k,
)
from core.settings import get_settings
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


def _connect_or_skip():
    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        connection = engine.connect()
    except SQLAlchemyError as exc:
        engine.dispose()
        pytest.skip(f"Postgres not available for integration test: {exc}")
    return engine, connection


def _unit_vector(dim: int, axis: int) -> list[float]:
    values = [0.0] * dim
    values[axis] = 1.0
    return values


def test_vector_similarity_retrieval_is_ranked_and_workspace_scoped() -> None:
    """Nearest-neighbor retrieval should rank by distance and isolate workspaces."""
    settings = get_settings()
    engine, connection = _connect_or_skip()
    transaction = connection.begin()
    session = Session(bind=connection)

    try:
        suffix = uuid4().hex
        user_id = int(
            session.execute(
                text("INSERT INTO users (email) VALUES (:email) RETURNING id"),
                {"email": f"vector-{suffix}@example.test"},
            ).scalar_one()
        )

        workspace_id_1 = int(
            session.execute(
                text(
                    "INSERT INTO workspaces (name, owner_user_id) "
                    "VALUES (:name, :owner_user_id) RETURNING id"
                ),
                {"name": f"ws-{suffix}-1", "owner_user_id": user_id},
            ).scalar_one()
        )
        workspace_id_2 = int(
            session.execute(
                text(
                    "INSERT INTO workspaces (name, owner_user_id) "
                    "VALUES (:name, :owner_user_id) RETURNING id"
                ),
                {"name": f"ws-{suffix}-2", "owner_user_id": user_id},
            ).scalar_one()
        )

        document_id_1 = int(
            session.execute(
                text(
                    "INSERT INTO documents "
                    "(workspace_id, uploaded_by_user_id, title, content_hash) "
                    "VALUES (:workspace_id, :uploaded_by_user_id, :title, :content_hash) "
                    "RETURNING id"
                ),
                {
                    "workspace_id": workspace_id_1,
                    "uploaded_by_user_id": user_id,
                    "title": "doc-1",
                    "content_hash": f"hash-{suffix}-1",
                },
            ).scalar_one()
        )
        document_id_2 = int(
            session.execute(
                text(
                    "INSERT INTO documents "
                    "(workspace_id, uploaded_by_user_id, title, content_hash) "
                    "VALUES (:workspace_id, :uploaded_by_user_id, :title, :content_hash) "
                    "RETURNING id"
                ),
                {
                    "workspace_id": workspace_id_2,
                    "uploaded_by_user_id": user_id,
                    "title": "doc-2",
                    "content_hash": f"hash-{suffix}-2",
                },
            ).scalar_one()
        )

        axis_0 = _unit_vector(settings.embedding_dim, 0)
        axis_1 = _unit_vector(settings.embedding_dim, 1)

        workspace_one_chunk_ids = insert_chunks_with_embeddings(
            session=session,
            rows=[
                ChunkInsertRow(
                    workspace_id=workspace_id_1,
                    document_id=document_id_1,
                    chunk_index=0,
                    text="closest",
                    embedding=axis_0,
                ),
                ChunkInsertRow(
                    workspace_id=workspace_id_1,
                    document_id=document_id_1,
                    chunk_index=1,
                    text="tie-first",
                    embedding=axis_1,
                ),
                ChunkInsertRow(
                    workspace_id=workspace_id_1,
                    document_id=document_id_1,
                    chunk_index=2,
                    text="tie-second",
                    embedding=axis_1,
                ),
            ],
        )

        workspace_two_chunk_ids = insert_chunks_with_embeddings(
            session=session,
            rows=[
                ChunkInsertRow(
                    workspace_id=workspace_id_2,
                    document_id=document_id_2,
                    chunk_index=0,
                    text="other-workspace",
                    embedding=axis_0,
                )
            ],
        )

        rows = vector_top_k(
            session=session,
            query_embedding=axis_0,
            workspace_id=workspace_id_1,
            top_k=3,
        )

        assert [row.chunk_id for row in rows] == workspace_one_chunk_ids
        assert [row.document_id for row in rows] == [document_id_1, document_id_1, document_id_1]

        other_rows = vector_top_k(
            session=session,
            query_embedding=axis_0,
            workspace_id=workspace_id_2,
            top_k=3,
        )

        assert [row.chunk_id for row in other_rows] == workspace_two_chunk_ids
        assert [row.document_id for row in other_rows] == [document_id_2]
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()
