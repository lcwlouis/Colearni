"""Integration test for graph extraction + online resolver canonical upserts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import uuid4

import pytest
from adapters.db.chunks import list_chunks_for_document
from core.contracts import GraphLLMClient
from core.settings import get_settings
from domain.graph.pipeline import build_graph_for_chunks
from domain.graph.types import normalize_alias
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class IntegrationGraphLLM(GraphLLMClient):
    """Deterministic graph LLM test double."""

    def extract_raw_graph(self, *, chunk_text: str) -> Mapping[str, Any]:
        return {
            "concepts": [
                {
                    "name": "Vector Space",
                    "context_snippet": "Vector spaces define linear structure.",
                    "description": "A set closed under addition and scalar multiplication.",
                },
                {
                    "name": "Linear Independence",
                    "context_snippet": "Independent vectors are non-redundant.",
                    "description": "No vector can be formed by combining the others.",
                },
            ],
            "edges": [
                {
                    "src_name": "Vector Space",
                    "tgt_name": "Linear Independence",
                    "relation_type": "contains",
                    "description": "Vector spaces include concepts like linear independence.",
                    "keywords": ["basis", "independence"],
                    "weight": 1.0,
                }
            ],
        }

    def disambiguate(
        self,
        *,
        raw_name: str,
        context_snippet: str | None,
        candidates: Sequence[Mapping[str, object]],
    ) -> Mapping[str, Any]:
        return {"decision": "CREATE_NEW", "confidence": 1.0}

    def generate_tutor_text(self, *, prompt: str, prompt_meta=None) -> str:
        return "Integration test summary."


def _connect_or_skip() -> tuple[Any, Any]:
    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        connection = engine.connect()
    except SQLAlchemyError as exc:
        engine.dispose()
        pytest.skip(f"Postgres not available for integration test: {exc}")
    return engine, connection


def test_graph_builder_merge_create_provenance_and_edge_dedupe() -> None:
    """Graph builder should persist raw rows and upsert canonical rows idempotently."""
    settings = get_settings()
    engine, connection = _connect_or_skip()
    transaction = connection.begin()
    session = Session(bind=connection)

    try:
        unique_suffix = uuid4().hex
        user_id = int(
            session.execute(
                text("INSERT INTO users (email) VALUES (:email) RETURNING id"),
                {"email": f"graph-{unique_suffix}@example.test"},
            ).scalar_one()
        )
        workspace_id = int(
            session.execute(
                text(
                    "INSERT INTO workspaces (name, owner_user_id) "
                    "VALUES (:name, :owner_user_id) RETURNING id"
                ),
                {"name": f"graph-ws-{unique_suffix}", "owner_user_id": user_id},
            ).scalar_one()
        )
        document_id = int(
            session.execute(
                text(
                    "INSERT INTO documents "
                    "(workspace_id, uploaded_by_user_id, title, content_hash) "
                    "VALUES (:workspace_id, :uploaded_by_user_id, :title, :content_hash) "
                    "RETURNING id"
                ),
                {
                    "workspace_id": workspace_id,
                    "uploaded_by_user_id": user_id,
                    "title": "Graph Doc",
                    "content_hash": f"graph-hash-{unique_suffix}",
                },
            ).scalar_one()
        )
        chunk_id = int(
            session.execute(
                text(
                    """
                    INSERT INTO chunks (
                        workspace_id,
                        document_id,
                        chunk_index,
                        text,
                        tsv,
                        embedding
                    )
                    VALUES (
                        :workspace_id,
                        :document_id,
                        0,
                        :chunk_text,
                        to_tsvector('english', :chunk_text),
                        NULL
                    )
                    RETURNING id
                    """
                ),
                {
                    "workspace_id": workspace_id,
                    "document_id": document_id,
                    "chunk_text": (
                        "Vector spaces and linear independence are core to linear algebra."
                    ),
                },
            ).scalar_one()
        )
        existing_vector_space_id = int(
            session.execute(
                text(
                    """
                    INSERT INTO concepts_canon (
                        workspace_id,
                        canonical_name,
                        description,
                        aliases,
                        dirty,
                        is_active
                    )
                    VALUES (
                        :workspace_id,
                        :canonical_name,
                        :description,
                        :aliases,
                        FALSE,
                        TRUE
                    )
                    RETURNING id
                    """
                ),
                {
                    "workspace_id": workspace_id,
                    "canonical_name": "Vector Spaces",
                    "description": "Existing canonical vector-space concept.",
                    "aliases": ["Vectors"],
                },
            ).scalar_one()
        )
        session.execute(
            text(
                """
                INSERT INTO concept_merge_map (
                    workspace_id,
                    alias,
                    canon_concept_id,
                    confidence,
                    method
                )
                VALUES (
                    :workspace_id,
                    :alias,
                    :canon_concept_id,
                    1.0,
                    'manual'
                )
                """
            ),
            {
                "workspace_id": workspace_id,
                "alias": normalize_alias("Vector Space"),
                "canon_concept_id": existing_vector_space_id,
            },
        )

        chunks = list_chunks_for_document(
            session,
            workspace_id=workspace_id,
            document_id=document_id,
        )
        llm = IntegrationGraphLLM()

        first_result = build_graph_for_chunks(
            session,
            workspace_id=workspace_id,
            chunks=chunks,
            llm_client=llm,
            settings=settings,
            embedding_provider=None,
        )
        second_result = build_graph_for_chunks(
            session,
            workspace_id=workspace_id,
            chunks=chunks,
            llm_client=llm,
            settings=settings,
            embedding_provider=None,
        )

        assert first_result.raw_concepts_written == 2
        assert first_result.raw_edges_written == 1
        assert first_result.canonical_created >= 1
        assert first_result.canonical_merged >= 1
        assert second_result.canonical_edges_upserted == 1

        raw_concepts_count = int(
            session.execute(
                text(
                    "SELECT count(*) FROM concepts_raw "
                    "WHERE workspace_id = :workspace_id AND chunk_id = :chunk_id"
                ),
                {"workspace_id": workspace_id, "chunk_id": chunk_id},
            ).scalar_one()
        )
        raw_edges_count = int(
            session.execute(
                text(
                    "SELECT count(*) FROM edges_raw "
                    "WHERE workspace_id = :workspace_id AND chunk_id = :chunk_id"
                ),
                {"workspace_id": workspace_id, "chunk_id": chunk_id},
            ).scalar_one()
        )
        assert raw_concepts_count == 4  # two concepts written per run
        assert raw_edges_count == 2      # one edge written per run

        merged_dirty = bool(
            session.execute(
                text(
                    "SELECT dirty FROM concepts_canon "
                    "WHERE workspace_id = :workspace_id AND id = :concept_id"
                ),
                {
                    "workspace_id": workspace_id,
                    "concept_id": existing_vector_space_id,
                },
            ).scalar_one()
        )
        assert merged_dirty is True

        created_concept_id = int(
            session.execute(
                text(
                    """
                    SELECT id
                    FROM concepts_canon
                    WHERE workspace_id = :workspace_id
                      AND lower(canonical_name) = lower(:canonical_name)
                    """
                ),
                {"workspace_id": workspace_id, "canonical_name": "Linear Independence"},
            ).scalar_one()
        )
        created_dirty = bool(
            session.execute(
                text("SELECT dirty FROM concepts_canon WHERE id = :concept_id"),
                {"concept_id": created_concept_id},
            ).scalar_one()
        )
        assert created_dirty is True

        concept_provenance_count = int(
            session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM provenance
                    WHERE workspace_id = :workspace_id
                      AND chunk_id = :chunk_id
                      AND target_type = 'concept'
                    """
                ),
                {"workspace_id": workspace_id, "chunk_id": chunk_id},
            ).scalar_one()
        )
        assert concept_provenance_count == 2

        edge_row = session.execute(
            text(
                """
                SELECT id, weight, keywords
                FROM edges_canon
                WHERE workspace_id = :workspace_id
                """
            ),
            {"workspace_id": workspace_id},
        ).mappings().one()
        assert float(edge_row["weight"]) == pytest.approx(2.0)
        assert sorted(str(keyword) for keyword in edge_row["keywords"]) == ["basis", "independence"]

        edge_provenance_count = int(
            session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM provenance
                    WHERE workspace_id = :workspace_id
                      AND chunk_id = :chunk_id
                      AND target_type = 'edge'
                      AND target_id = :target_id
                    """
                ),
                {
                    "workspace_id": workspace_id,
                    "chunk_id": chunk_id,
                    "target_id": int(edge_row["id"]),
                },
            ).scalar_one()
        )
        assert edge_provenance_count == 1

        alias_map_count = int(
            session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM concept_merge_map
                    WHERE workspace_id = :workspace_id
                      AND alias = :alias
                    """
                ),
                {
                    "workspace_id": workspace_id,
                    "alias": normalize_alias("Linear Independence"),
                },
            ).scalar_one()
        )
        assert alias_map_count == 1
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()
