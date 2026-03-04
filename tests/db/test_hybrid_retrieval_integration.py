"""Integration tests for hybrid vector + FTS retrieval."""

from __future__ import annotations

from uuid import uuid4

from adapters.db.chunks_repository import ChunkInsertRow, insert_chunks_with_embeddings
from core.contracts import EmbeddingProvider
from core.settings import get_settings
from domain.retrieval.fts_retriever import PgFtsRetriever
from domain.retrieval.hybrid_retriever import HybridRetriever
from domain.retrieval.vector_retriever import PgVectorRetriever
from sqlalchemy import text
from sqlalchemy.orm import Session
from tests.db.test_vector_similarity_integration import _connect_or_skip

INSERT_DOCUMENT_SQL = (
    "INSERT INTO documents (workspace_id, uploaded_by_user_id, title, content_hash) "
    "VALUES (:workspace_id, :uploaded_by_user_id, :title, :content_hash) RETURNING id"
)


class FixedProvider(EmbeddingProvider):
    def __init__(self, embedding: list[float]) -> None:
        self._embedding = embedding

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embedding for _ in texts]


def _insert_id(session: Session, statement: str, **params: object) -> int:
    return int(session.execute(text(statement), params).scalar_one())


def _insert_document(
    session: Session,
    workspace_id: int,
    user_id: int,
    title: str,
    content_hash: str,
) -> int:
    return _insert_id(
        session,
        INSERT_DOCUMENT_SQL,
        workspace_id=workspace_id,
        uploaded_by_user_id=user_id,
        title=title,
        content_hash=content_hash,
    )


def test_hybrid_retrieval_combines_vector_and_fts_with_workspace_scoping() -> None:
    settings = get_settings()
    engine, connection = _connect_or_skip()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        suffix = uuid4().hex
        user_id = _insert_id(
            session,
            "INSERT INTO users (email) VALUES (:email) RETURNING id",
            email=f"hybrid-{suffix}@example.test",
        )
        workspace_id_1, workspace_id_2 = [
            _insert_id(
                session,
                "INSERT INTO workspaces (name, owner_user_id) VALUES (:name, :owner_user_id) "
                "RETURNING id",
                name=f"hybrid-{suffix}-{idx}",
                owner_user_id=user_id,
            )
            for idx in (1, 2)
        ]
        document_id_1a, document_id_1b, document_id_2 = [
            _insert_document(session, workspace_id, user_id, title, content_hash)
            for workspace_id, title, content_hash in [
                (workspace_id_1, "doc-1a", f"hash-{suffix}-1a"),
                (workspace_id_1, "doc-1b", f"hash-{suffix}-1b"),
                (workspace_id_2, "doc-2", f"hash-{suffix}-2"),
            ]
        ]

        axis_0 = [0.0] * settings.embedding_dim
        axis_0[0] = 1.0
        near_axis_0 = axis_0.copy()
        near_axis_0[0], near_axis_0[1] = 0.8, 0.2

        chunk_vector_only_id, chunk_hybrid_id = insert_chunks_with_embeddings(
            session=session,
            rows=[
                ChunkInsertRow(workspace_id_1, document_id_1a, 0, "linear algebra basis", axis_0),
                ChunkInsertRow(
                    workspace_id_1,
                    document_id_1a,
                    1,
                    "entropy in information theory",
                    near_axis_0,
                ),
            ],
        )
        chunk_fts_only_id = _insert_id(
            session,
            "INSERT INTO chunks (workspace_id, document_id, chunk_index, text, tsv, embedding) "
            "VALUES ("
            ":workspace_id, :document_id, :chunk_index, :text, to_tsvector('english', :text), NULL"
            ") RETURNING id",
            workspace_id=workspace_id_1,
            document_id=document_id_1b,
            chunk_index=0,
            text="entropy entropy glossary",
        )
        insert_chunks_with_embeddings(
            session=session,
            rows=[
                ChunkInsertRow(
                    workspace_id_2, document_id_2, 0, "other-workspace entropy notes", axis_0
                )
            ],
        )

        retriever = HybridRetriever(
            vector_retriever=PgVectorRetriever(session, FixedProvider(axis_0), 10),
            fts_retriever=PgFtsRetriever(session, 10),
            retrieval_max_top_k=10,
        )
        ranked = retriever.retrieve(query="entropy", workspace_id=workspace_id_1, top_k=3)

        assert [row.chunk_id for row in ranked] == [
            chunk_hybrid_id,
            chunk_vector_only_id,
            chunk_fts_only_id,
        ]
        assert [row.retrieval_method for row in ranked] == ["hybrid", "vector", "fts"]
        assert all(row.workspace_id == workspace_id_1 for row in ranked)
        assert all(row.document_id in {document_id_1a, document_id_1b} for row in ranked)
        assert not any("other-workspace" in row.text for row in ranked)
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()
