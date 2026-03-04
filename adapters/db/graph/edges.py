"""Canonical edge operations."""

from __future__ import annotations

from collections.abc import Sequence

from domain.graph.types import ExtractedEdge, dedupe_keywords, truncate_text
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from adapters.db.graph import CanonicalEdgeRepointRow, CanonicalEdgeRow


def insert_raw_edges(
    session: Session,
    *,
    workspace_id: int,
    chunk_id: int,
    edges: Sequence[ExtractedEdge],
) -> int:
    """Insert raw edges for a chunk and return inserted count."""
    if not edges:
        return 0

    rows = [
        {
            "workspace_id": workspace_id,
            "chunk_id": chunk_id,
            "src_name": edge.src_name,
            "tgt_name": edge.tgt_name,
            "relation_type": edge.relation_type,
            "description": edge.description,
            "keywords": edge.keywords,
            "weight": edge.weight,
        }
        for edge in edges
    ]
    session.execute(
        text(
            """
            INSERT INTO edges_raw (
                workspace_id,
                chunk_id,
                src_name,
                tgt_name,
                relation_type,
                description,
                keywords,
                weight
            )
            VALUES (
                :workspace_id,
                :chunk_id,
                :src_name,
                :tgt_name,
                :relation_type,
                :description,
                :keywords,
                :weight
            )
            """
        ),
        rows,
    )
    return len(rows)


def repoint_edges_for_merge(
    session: Session,
    *,
    workspace_id: int,
    from_id: int,
    to_id: int,
    weight_cap: float,
    edge_description_max_chars: int,
) -> int:
    """Move all edges touching from_id to to_id, deduping via canonical edge upsert."""
    if from_id == to_id:
        return 0

    rows = (
        session.execute(
            text(
                """
                SELECT
                    id,
                    src_id,
                    tgt_id,
                    relation_type,
                    description,
                    keywords,
                    weight
                FROM edges_canon
                WHERE workspace_id = :workspace_id
                  AND (src_id = :from_id OR tgt_id = :from_id)
                ORDER BY id ASC
                """
            ),
            {"workspace_id": workspace_id, "from_id": from_id},
        )
        .mappings()
        .all()
    )
    edges = [
        CanonicalEdgeRepointRow(
            id=int(row["id"]),
            src_id=int(row["src_id"]),
            tgt_id=int(row["tgt_id"]),
            relation_type=str(row["relation_type"]),
            description=str(row["description"] or ""),
            keywords=[str(keyword) for keyword in (row["keywords"] or [])],
            weight=float(row["weight"]),
        )
        for row in rows
    ]
    if not edges:
        return 0

    session.execute(
        text("DELETE FROM edges_canon WHERE id IN :edge_ids").bindparams(
            bindparam("edge_ids", expanding=True)
        ),
        {"edge_ids": [edge.id for edge in edges]},
    )

    upserts = 0
    for edge in edges:
        new_src = to_id if edge.src_id == from_id else edge.src_id
        new_tgt = to_id if edge.tgt_id == from_id else edge.tgt_id
        if new_src == new_tgt:
            continue
        upsert_canonical_edge(
            session,
            workspace_id=workspace_id,
            src_id=new_src,
            tgt_id=new_tgt,
            relation_type=edge.relation_type,
            description=edge.description,
            keywords=edge.keywords,
            delta_weight=edge.weight,
            weight_cap=weight_cap,
            edge_description_max_chars=edge_description_max_chars,
        )
        upserts += 1
    return upserts


def upsert_canonical_edge(
    session: Session,
    *,
    workspace_id: int,
    src_id: int,
    tgt_id: int,
    relation_type: str,
    description: str,
    keywords: Sequence[str],
    delta_weight: float,
    weight_cap: float,
    edge_description_max_chars: int,
) -> int:
    """Upsert canonical edge, merging keywords/description/weight deterministically."""
    existing_row = (
        session.execute(
            text(
                """
                SELECT id, description, keywords, weight
                FROM edges_canon
                WHERE workspace_id = :workspace_id
                  AND src_id = :src_id
                  AND tgt_id = :tgt_id
                  AND relation_type = :relation_type
                """
            ),
            {
                "workspace_id": workspace_id,
                "src_id": src_id,
                "tgt_id": tgt_id,
                "relation_type": relation_type,
            },
        )
        .mappings()
        .first()
    )
    incoming_description = truncate_text(description, edge_description_max_chars)
    incoming_keywords = dedupe_keywords(list(keywords))
    incoming_weight = max(0.0, float(delta_weight))

    if existing_row is None:
        edge_id = int(
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
                        :src_id,
                        :tgt_id,
                        :relation_type,
                        :description,
                        :keywords,
                        :weight
                    )
                    RETURNING id
                    """
                ),
                {
                    "workspace_id": workspace_id,
                    "src_id": src_id,
                    "tgt_id": tgt_id,
                    "relation_type": relation_type,
                    "description": incoming_description,
                    "keywords": incoming_keywords,
                    "weight": min(incoming_weight, weight_cap),
                },
            ).scalar_one()
        )
        return edge_id

    existing = CanonicalEdgeRow(
        id=int(existing_row["id"]),
        description=str(existing_row["description"] or ""),
        keywords=[str(keyword) for keyword in (existing_row["keywords"] or [])],
        weight=float(existing_row["weight"]),
    )
    merged_description = (
        incoming_description
        if len(incoming_description) > len(existing.description)
        else existing.description
    )
    merged_keywords = dedupe_keywords(existing.keywords + incoming_keywords)
    merged_weight = min(existing.weight + incoming_weight, weight_cap)

    session.execute(
        text(
            """
            UPDATE edges_canon
            SET
                description = :description,
                keywords = :keywords,
                weight = :weight,
                updated_at = now()
            WHERE id = :edge_id
            """
        ),
        {
            "edge_id": existing.id,
            "description": merged_description,
            "keywords": merged_keywords,
            "weight": merged_weight,
        },
    )
    return existing.id
