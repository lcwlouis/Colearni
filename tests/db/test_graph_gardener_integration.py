"""Integration test for offline graph gardener merge consolidation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from uuid import uuid4

import pytest
from core.contracts import GraphLLMClient
from core.settings import get_settings
from domain.graph.gardener import run_graph_gardener
from domain.graph.types import normalize_alias
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class IntegrationGardenerLLM(GraphLLMClient):
    """Deterministic LLM test double for cluster merge decisions."""

    def __init__(self, merge_into_id: int) -> None:
        self._merge_into_id = merge_into_id

    def extract_raw_graph(self, *, chunk_text: str) -> Mapping[str, Any]:
        return {"concepts": [], "edges": []}

    def disambiguate(
        self,
        *,
        raw_name: str,
        context_snippet: str | None,
        candidates: Sequence[Mapping[str, object]],
    ) -> Mapping[str, Any]:
        return {
            "decision": "MERGE_INTO",
            "merge_into_id": self._merge_into_id,
            "confidence": 0.92,
        }

    def disambiguate_batch(
        self,
        *,
        items: Sequence[Mapping[str, object]],
    ) -> Sequence[Mapping[str, Any]]:
        return [
            {
                "concept_ref": str(item.get("raw_name", "")),
                "operations": [
                    {
                        "decision": "MERGE_INTO",
                        "merge_into_id": self._merge_into_id,
                        "confidence": 0.92,
                    }
                ],
            }
            for item in items
        ]

    def generate_tutor_text(self, *, prompt: str, prompt_meta=None, system_prompt=None) -> str:
        return prompt


def _connect_or_skip() -> tuple[Any, Any]:
    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        connection = engine.connect()
    except SQLAlchemyError as exc:
        engine.dispose()
        pytest.skip(f"Postgres not available for integration test: {exc}")
    return engine, connection


def test_graph_gardener_merge_bookkeeping_and_idempotency() -> None:
    """Gardener should merge once, update bookkeeping, and no-op on replay."""
    settings = get_settings().model_copy(
        update={
            "gardener_max_llm_calls_per_run": 10,
            "gardener_max_clusters_per_run": 10,
            "gardener_max_dirty_nodes_per_run": 200,
            "gardener_recent_window_days": 7,
            "resolver_lexical_top_k": 5,
            "resolver_vector_top_k": 10,
            "resolver_candidate_cap": 10,
        }
    )
    engine, connection = _connect_or_skip()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        unique = uuid4().hex
        user_id = int(
            session.execute(
                text("INSERT INTO users (email) VALUES (:email) RETURNING id"),
                {"email": f"gardener-{unique}@example.test"},
            ).scalar_one()
        )
        workspace_id = int(
            session.execute(
                text(
                    "INSERT INTO workspaces (name, owner_user_id) "
                    "VALUES (:name, :owner_user_id) RETURNING id"
                ),
                {"name": f"gardener-ws-{unique}", "owner_user_id": user_id},
            ).scalar_one()
        )
        keep_id = int(
            session.execute(
                text(
                    """
                    INSERT INTO concepts_canon (
                        workspace_id,
                        canonical_name,
                        description,
                        aliases,
                        is_active,
                        dirty,
                        embedding,
                        tier
                    )
                    VALUES (
                        :workspace_id,
                        'Vector Space',
                        'Keep',
                        :aliases,
                        TRUE,
                        TRUE,
                        NULL,
                        'topic'
                    )
                    RETURNING id
                    """
                ),
                {"workspace_id": workspace_id, "aliases": ["Vector Space", "VS"]},
            ).scalar_one()
        )
        merge_away_id = int(
            session.execute(
                text(
                    """
                    INSERT INTO concepts_canon (
                        workspace_id,
                        canonical_name,
                        description,
                        aliases,
                        is_active,
                        dirty,
                        embedding,
                        tier
                    )
                    VALUES (
                        :workspace_id,
                        'Vector Spaces',
                        'Duplicate',
                        :aliases,
                        TRUE,
                        TRUE,
                        NULL,
                        'topic'
                    )
                    RETURNING id
                    """
                ),
                {"workspace_id": workspace_id, "aliases": ["Vector Spaces"]},
            ).scalar_one()
        )
        neighbor_id = int(
            session.execute(
                text(
                    """
                    INSERT INTO concepts_canon (
                        workspace_id,
                        canonical_name,
                        description,
                        aliases,
                        is_active,
                        dirty,
                        embedding,
                        tier
                    )
                    VALUES (
                        :workspace_id,
                        'Linear Independence',
                        'Neighbor',
                        :aliases,
                        TRUE,
                        FALSE,
                        NULL,
                        'subtopic'
                    )
                    RETURNING id
                    """
                ),
                {"workspace_id": workspace_id, "aliases": ["Linear Independence"]},
            ).scalar_one()
        )
        session.execute(
            text(
                """
                UPDATE concepts_canon
                SET updated_at = now() - interval '30 days'
                WHERE workspace_id = :workspace_id
                  AND id = :concept_id
                """
            ),
            {"workspace_id": workspace_id, "concept_id": neighbor_id},
        )

        # Create provenance for keep_id so it is not pruned as orphan
        doc_id = int(
            session.execute(
                text(
                    "INSERT INTO documents (workspace_id, uploaded_by_user_id, title, content_hash)"
                    " VALUES (:wid, :uid, 'stub', :hash) RETURNING id"
                ),
                {"wid": workspace_id, "uid": user_id, "hash": unique},
            ).scalar_one()
        )
        chunk_id = int(
            session.execute(
                text(
                    "INSERT INTO chunks (workspace_id, document_id, chunk_index, text)"
                    " VALUES (:wid, :did, 0, 'stub') RETURNING id"
                ),
                {"wid": workspace_id, "did": doc_id},
            ).scalar_one()
        )
        session.execute(
            text(
                "INSERT INTO provenance (workspace_id, target_type, target_id, chunk_id)"
                " VALUES (:wid, 'concept', :tid, :cid)"
            ),
            {"wid": workspace_id, "tid": keep_id, "cid": chunk_id},
        )
        session.execute(
            text(
                "INSERT INTO provenance (workspace_id, target_type, target_id, chunk_id)"
                " VALUES (:wid, 'concept', :tid, :cid)"
            ),
            {"wid": workspace_id, "tid": neighbor_id, "cid": chunk_id},
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
                VALUES
                    (:workspace_id, :alias_keep, :keep_id, 1.0, 'manual'),
                    (:workspace_id, :alias_keep_short, :keep_id, 1.0, 'manual'),
                    (:workspace_id, :alias_merge_away, :merge_away_id, 1.0, 'manual')
                """
            ),
            {
                "workspace_id": workspace_id,
                "alias_keep": normalize_alias("Vector Space"),
                "alias_keep_short": normalize_alias("VS"),
                "keep_id": keep_id,
                "alias_merge_away": normalize_alias("Vector Spaces"),
                "merge_away_id": merge_away_id,
            },
        )

        edge_keep_id = int(
            session.execute(
                text(
                    """
                    INSERT INTO edges_canon (
                        workspace_id,
                        src_id,
                        tgt_id,
                        relation_type,
                        description,
                        keywords,
                        weight
                    )
                    VALUES (
                        :workspace_id,
                        :keep_id,
                        :neighbor_id,
                        'contains',
                        'edge-keep',
                        '{basis}'::text[],
                        1.0
                    )
                    RETURNING id
                    """
                ),
                {
                    "workspace_id": workspace_id,
                    "keep_id": keep_id,
                    "neighbor_id": neighbor_id,
                },
            ).scalar_one()
        )
        session.execute(
            text(
                """
                INSERT INTO edges_canon (
                    workspace_id,
                    src_id,
                    tgt_id,
                    relation_type,
                    description,
                    keywords,
                    weight
                )
                VALUES (
                    :workspace_id,
                    :merge_away_id,
                    :neighbor_id,
                    'contains',
                    'edge-dup',
                    '{independence}'::text[],
                    2.0
                )
                """
            ),
            {
                "workspace_id": workspace_id,
                "merge_away_id": merge_away_id,
                "neighbor_id": neighbor_id,
            },
        )
        session.execute(
            text(
                "INSERT INTO provenance (workspace_id, target_type, target_id, chunk_id)"
                " VALUES (:wid, 'edge', :tid, :cid)"
            ),
            {"wid": workspace_id, "tid": edge_keep_id, "cid": chunk_id},
        )

        llm = IntegrationGardenerLLM(merge_into_id=keep_id)
        first = run_graph_gardener(
            session,
            workspace_id=workspace_id,
            llm_client=llm,
            settings=settings,
        )
        second = run_graph_gardener(
            session,
            workspace_id=workspace_id,
            llm_client=llm,
            settings=settings,
        )

        assert first.merges_applied == 1
        assert first.llm_calls == 1
        assert second.merges_applied == 0

        merged_away_active = bool(
            session.execute(
                text(
                    "SELECT is_active FROM concepts_canon "
                    "WHERE workspace_id = :workspace_id AND id = :concept_id"
                ),
                {"workspace_id": workspace_id, "concept_id": merge_away_id},
            ).scalar_one()
        )
        assert merged_away_active is False

        merge_log_count = int(
            session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM concept_merge_log
                    WHERE workspace_id = :workspace_id
                      AND from_id = :from_id
                      AND to_id = :to_id
                    """
                ),
                {"workspace_id": workspace_id, "from_id": merge_away_id, "to_id": keep_id},
            ).scalar_one()
        )
        assert merge_log_count == 1

        alias_target_id = int(
            session.execute(
                text(
                    """
                    SELECT canon_concept_id
                    FROM concept_merge_map
                    WHERE workspace_id = :workspace_id
                      AND alias = :alias
                    """
                ),
                {
                    "workspace_id": workspace_id,
                    "alias": normalize_alias("Vector Spaces"),
                },
            ).scalar_one()
        )
        assert alias_target_id == keep_id

        edge_count = int(
            session.execute(
                text(
                    """
                    SELECT count(*)
                    FROM edges_canon
                    WHERE workspace_id = :workspace_id
                      AND src_id = :src_id
                      AND tgt_id = :tgt_id
                      AND relation_type = 'contains'
                    """
                ),
                {"workspace_id": workspace_id, "src_id": keep_id, "tgt_id": neighbor_id},
            ).scalar_one()
        )
        assert edge_count == 1

        merged_edge_weight = float(
            session.execute(
                text(
                    """
                    SELECT weight
                    FROM edges_canon
                    WHERE workspace_id = :workspace_id
                      AND src_id = :src_id
                      AND tgt_id = :tgt_id
                      AND relation_type = 'contains'
                    """
                ),
                {"workspace_id": workspace_id, "src_id": keep_id, "tgt_id": neighbor_id},
            ).scalar_one()
        )
        assert merged_edge_weight == pytest.approx(3.0)
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()
