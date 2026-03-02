"""Shared quiz persistence helpers.

DB-level quiz reads and writes used across quiz flows (level-up, practice,
and chat context enrichment).  Orchestration logic, validation ordering,
observability, and policy decisions stay in :mod:`quiz_flow`.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Concept lookup
# ---------------------------------------------------------------------------

def lookup_active_concept(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
) -> Any | None:
    """Return the active concept row or *None*."""
    return (
        session.execute(
            text(
                """
                SELECT canonical_name, description
                FROM concepts_canon
                WHERE id = :concept_id AND workspace_id = :workspace_id AND is_active = TRUE
                LIMIT 1
                """
            ),
            {"concept_id": concept_id, "workspace_id": workspace_id},
        )
        .mappings()
        .first()
    )


# ---------------------------------------------------------------------------
# Quiz CRUD
# ---------------------------------------------------------------------------

def insert_quiz_row(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    session_id: int | None,
    concept_id: int,
    quiz_type: str,
) -> Any:
    """Insert a quiz row and return the mapping with ``id`` and ``status``."""
    return (
        session.execute(
            text(
                """
                INSERT INTO quizzes (
                    workspace_id, user_id, session_id, concept_id, quiz_type, status
                )
                VALUES (:workspace_id, :user_id, :session_id, :concept_id, :quiz_type, 'ready')
                RETURNING id, status
                """
            ),
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "session_id": session_id,
                "concept_id": concept_id,
                "quiz_type": quiz_type,
            },
        )
        .mappings()
        .one()
    )


def insert_quiz_items(
    session: Session,
    *,
    quiz_id: int,
    items: list[dict[str, Any]],
) -> None:
    """Bulk-insert quiz item rows."""
    session.execute(
        text(
            """
            INSERT INTO quiz_items (quiz_id, position, item_type, prompt, payload)
            VALUES (:quiz_id, :position, :item_type, :prompt, CAST(:payload AS jsonb))
            """
        ),
        [
            {
                "quiz_id": quiz_id,
                "position": idx,
                "item_type": item["item_type"],
                "prompt": item["prompt"],
                "payload": json.dumps(item["payload"], ensure_ascii=True),
            }
            for idx, item in enumerate(items, start=1)
        ],
    )


def load_quiz_items(
    session: Session,
    *,
    quiz_id: int,
) -> list[Any]:
    """Load quiz items ordered by position."""
    return (
        session.execute(
            text(
                """
                SELECT id AS item_id, position, item_type, prompt, payload
                FROM quiz_items
                WHERE quiz_id = :quiz_id
                ORDER BY position
                """
            ),
            {"quiz_id": quiz_id},
        )
        .mappings()
        .all()
    )


# ---------------------------------------------------------------------------
# Submission helpers
# ---------------------------------------------------------------------------

def load_quiz_for_grading(
    session: Session,
    *,
    quiz_id: int,
    workspace_id: int,
    quiz_type: str,
) -> Any | None:
    """Load a quiz row with ``FOR UPDATE`` lock, or *None*."""
    return (
        session.execute(
            text(
                """
                SELECT id, user_id, concept_id
                FROM quizzes
                WHERE id = :quiz_id
                  AND workspace_id = :workspace_id
                  AND quiz_type = :quiz_type
                FOR UPDATE
                """
            ),
            {"quiz_id": quiz_id, "workspace_id": workspace_id, "quiz_type": quiz_type},
        )
        .mappings()
        .first()
    )


def load_existing_graded_attempt(
    session: Session,
    *,
    quiz_id: int,
    user_id: int,
) -> Any | None:
    """Return the first graded attempt for the quiz, or *None*."""
    return (
        session.execute(
            text(
                """
                SELECT id, score, passed, grading
                FROM quiz_attempts
                WHERE quiz_id = :quiz_id AND user_id = :user_id AND graded_at IS NOT NULL
                ORDER BY id
                LIMIT 1
                """
            ),
            {"quiz_id": quiz_id, "user_id": user_id},
        )
        .mappings()
        .first()
    )


def lookup_mastery(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    concept_id: int,
) -> Any | None:
    """Return the mastery row or *None*."""
    return (
        session.execute(
            text(
                """
                SELECT status, score
                FROM mastery
                WHERE workspace_id = :workspace_id
                  AND user_id = :user_id
                  AND concept_id = :concept_id
                LIMIT 1
                """
            ),
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "concept_id": concept_id,
            },
        )
        .mappings()
        .first()
    )


def insert_attempt(
    session: Session,
    *,
    quiz_id: int,
    user_id: int,
    answers: list[dict[str, Any]],
    grading_payload: dict[str, Any],
    score: float,
    passed: bool,
) -> int:
    """Insert a quiz attempt and return the new attempt id."""
    session.execute(
        text(
            """
            INSERT INTO quiz_attempts (
                quiz_id, user_id, answers, grading, score, passed, graded_at
            )
            VALUES (
                :quiz_id, :user_id,
                CAST(:answers AS jsonb),
                CAST(:grading AS jsonb),
                :score, :passed, now()
            )
            """
        ),
        {
            "quiz_id": quiz_id,
            "user_id": user_id,
            "answers": json.dumps({"answers": answers}, ensure_ascii=True),
            "grading": json.dumps(grading_payload, ensure_ascii=True),
            "score": score,
            "passed": passed,
        },
    )
    return int(
        session.execute(text("SELECT currval('quiz_attempts_id_seq')")).scalar_one()
    )


def mark_quiz_graded(session: Session, *, quiz_id: int) -> None:
    """Set quiz status to ``'graded'``."""
    session.execute(
        text(
            "UPDATE quizzes "
            "SET status = 'graded', updated_at = now() "
            "WHERE id = :quiz_id"
        ),
        {"quiz_id": quiz_id},
    )


def lookup_concept_tier(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
) -> str | None:
    """Return the tier of an active concept, or *None*."""
    row = (
        session.execute(
            text(
                """
                SELECT tier
                FROM concepts_canon
                WHERE id = :concept_id AND workspace_id = :workspace_id AND is_active = TRUE
                LIMIT 1
                """
            ),
            {"concept_id": concept_id, "workspace_id": workspace_id},
        )
        .mappings()
        .first()
    )
    return str(row["tier"]) if row and row["tier"] is not None else None


def get_child_concept_ids(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
) -> list[int]:
    """Return IDs of direct child concepts via ``has_subtopic`` / ``belongs_to`` edges."""
    rows = (
        session.execute(
            text(
                """
                SELECT DISTINCT child_id FROM (
                    SELECT e.tgt_id AS child_id
                    FROM edges_canon e
                    JOIN concepts_canon c
                      ON c.id = e.tgt_id
                     AND c.workspace_id = e.workspace_id
                     AND c.is_active = TRUE
                    WHERE e.workspace_id = :workspace_id
                      AND e.src_id = :concept_id
                      AND e.relation_type = 'has_subtopic'

                    UNION

                    SELECT e.src_id AS child_id
                    FROM edges_canon e
                    JOIN concepts_canon c
                      ON c.id = e.src_id
                     AND c.workspace_id = e.workspace_id
                     AND c.is_active = TRUE
                    WHERE e.workspace_id = :workspace_id
                      AND e.tgt_id = :concept_id
                      AND e.relation_type = 'belongs_to'
                ) children
                """
            ),
            {"workspace_id": workspace_id, "concept_id": concept_id},
        )
        .mappings()
        .all()
    )
    return [int(row["child_id"]) for row in rows]


def upsert_mastery(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    concept_id: int,
    score: float,
    status: str,
) -> None:
    """Insert or update the mastery record."""
    session.execute(
        text(
            """
            INSERT INTO mastery (workspace_id, user_id, concept_id, score, status)
            VALUES (:workspace_id, :user_id, :concept_id, :score, :status)
            ON CONFLICT (user_id, concept_id)
            DO UPDATE SET
                workspace_id = EXCLUDED.workspace_id,
                score = EXCLUDED.score,
                status = EXCLUDED.status,
                updated_at = now()
            """
        ),
        {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "concept_id": concept_id,
            "score": score,
            "status": status,
        },
    )


# ---------------------------------------------------------------------------
# Generation context
# ---------------------------------------------------------------------------

def load_generation_context(
    session: Session,
    *,
    workspace_id: int,
    concept_id: int,
) -> dict[str, Any] | None:
    """Load concept, adjacent concepts, and chunk excerpts for quiz generation.

    Returns *None* if the concept is not found or inactive.
    """
    concept = lookup_active_concept(
        session, workspace_id=workspace_id, concept_id=concept_id
    )
    if concept is None:
        return None

    rows = (
        session.execute(
            text(
                """
                SELECT src.canonical_name AS src_name, tgt.canonical_name AS tgt_name
                FROM edges_canon e
                JOIN concepts_canon src ON src.id = e.src_id
                JOIN concepts_canon tgt ON tgt.id = e.tgt_id
                WHERE e.workspace_id = :workspace_id
                  AND ((e.src_id = :concept_id AND tgt.is_active = TRUE)
                       OR (e.tgt_id = :concept_id AND src.is_active = TRUE))
                ORDER BY e.weight DESC, e.id ASC
                LIMIT 8
                """
            ),
            {"workspace_id": workspace_id, "concept_id": concept_id},
        )
        .mappings()
        .all()
    )

    concept_name = str(concept["canonical_name"])
    adjacent = [
        str(row["tgt_name"]) if str(row["src_name"]) == concept_name else str(row["src_name"])
        for row in rows
    ]
    chunk_rows = (
        session.execute(
            text(
                """
                SELECT ch.text
                FROM provenance p
                JOIN chunks ch ON ch.id = p.chunk_id AND ch.workspace_id = p.workspace_id
                WHERE p.workspace_id = :workspace_id
                  AND p.target_type = 'concept'
                  AND p.target_id = :concept_id
                ORDER BY p.chunk_id ASC
                LIMIT 3
                """
            ),
            {"workspace_id": workspace_id, "concept_id": concept_id},
        )
        .mappings()
        .all()
    )
    chunk_excerpts = [str(r["text"])[:300] for r in chunk_rows]
    return {
        "concept_name": concept_name,
        "concept_description": str(concept["description"] or ""),
        "adjacent_concepts": adjacent,
        "chunk_excerpts": chunk_excerpts,
    }


# ---------------------------------------------------------------------------
# Session scope check
# ---------------------------------------------------------------------------

def check_session_scope(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    session_id: int,
) -> bool:
    """Return *True* if session_id is valid for the given workspace/user."""
    row = (
        session.execute(
            text(
                """
                SELECT id
                FROM chat_sessions
                WHERE id = :session_id
                  AND workspace_id = :workspace_id
                  AND user_id = :user_id
                LIMIT 1
                """
            ),
            {
                "session_id": session_id,
                "workspace_id": workspace_id,
                "user_id": user_id,
            },
        )
        .mappings()
        .first()
    )
    return row is not None


# ---------------------------------------------------------------------------
# Summary (existing)
# ---------------------------------------------------------------------------

def get_latest_quiz_summary_for_concept(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    concept_id: int,
) -> dict[str, Any] | None:
    """Return a summary of the latest quiz attempt for a given concept.

    Used by the tutor prompt to include recent quiz context in conversation.
    Returns None if no quiz has been attempted for this concept.
    """
    row = (
        session.execute(
            text(
                """
                SELECT q.id AS quiz_id,
                       q.status AS quiz_status,
                       qa.score,
                       qa.passed,
                       qa.graded_at,
                       qa.grading
                FROM quizzes q
                LEFT JOIN quiz_attempts qa
                  ON qa.quiz_id = q.id
                 AND qa.user_id = :user_id
                 AND qa.graded_at IS NOT NULL
                WHERE q.workspace_id = :workspace_id
                  AND q.user_id = :user_id
                  AND q.concept_id = :concept_id
                ORDER BY q.id DESC
                LIMIT 1
                """
            ),
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "concept_id": concept_id,
            },
        )
        .mappings()
        .first()
    )
    if row is None:
        return None

    grading = row["grading"] if isinstance(row["grading"], dict) else {}
    return {
        "quiz_id": int(row["quiz_id"]),
        "quiz_status": str(row["quiz_status"]),
        "score": float(row["score"]) if row["score"] is not None else None,
        "passed": bool(row["passed"]) if row["passed"] is not None else None,
        "overall_feedback": str(grading.get("overall_feedback", "")).strip()[:200],
        "attempted": row["graded_at"] is not None,
    }


def list_quizzes_with_latest_attempt(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    quiz_type: str,
    concept_id: int | None = None,
    limit: int = 20,
) -> list[Any]:
    """List quizzes with concept info + latest graded attempt summary."""
    safe_limit = max(1, min(limit, 100))
    params: dict[str, Any] = {
        "workspace_id": workspace_id,
        "user_id": user_id,
        "quiz_type": quiz_type,
        "limit": safe_limit,
    }
    concept_filter = ""
    if concept_id is not None:
        concept_filter = "AND q.concept_id = :concept_id"
        params["concept_id"] = concept_id

    return (
        session.execute(
            text(
                f"""
                SELECT
                    q.id AS quiz_id,
                    q.workspace_id,
                    q.user_id,
                    q.concept_id,
                    cc.canonical_name AS concept_name,
                    q.status,
                    q.created_at,
                    COALESCE(qi.item_count, 0) AS item_count,
                    qa.id AS attempt_id,
                    qa.score,
                    qa.passed,
                    qa.grading,
                    qa.graded_at
                FROM quizzes q
                LEFT JOIN concepts_canon cc ON cc.id = q.concept_id
                LEFT JOIN LATERAL (
                    SELECT count(*)::int AS item_count
                    FROM quiz_items i
                    WHERE i.quiz_id = q.id
                ) qi ON TRUE
                LEFT JOIN LATERAL (
                    SELECT id, score, passed, grading, graded_at
                    FROM quiz_attempts a
                    WHERE a.quiz_id = q.id
                      AND a.user_id = :user_id
                      AND a.graded_at IS NOT NULL
                    ORDER BY a.id DESC
                    LIMIT 1
                ) qa ON TRUE
                WHERE q.workspace_id = :workspace_id
                  AND q.user_id = :user_id
                  AND q.quiz_type = :quiz_type
                  {concept_filter}
                ORDER BY q.id DESC
                LIMIT :limit
                """
            ),
            params,
        )
        .mappings()
        .all()
    )


def load_quiz_with_latest_attempt(
    session: Session,
    *,
    workspace_id: int,
    user_id: int,
    quiz_id: int,
    quiz_type: str,
) -> Any | None:
    """Load one quiz row with concept info + latest graded attempt summary."""
    return (
        session.execute(
            text(
                """
                SELECT
                    q.id AS quiz_id,
                    q.workspace_id,
                    q.user_id,
                    q.concept_id,
                    cc.canonical_name AS concept_name,
                    q.status,
                    q.created_at,
                    COALESCE(qi.item_count, 0) AS item_count,
                    qa.id AS attempt_id,
                    qa.score,
                    qa.passed,
                    qa.grading,
                    qa.graded_at
                FROM quizzes q
                LEFT JOIN concepts_canon cc ON cc.id = q.concept_id
                LEFT JOIN LATERAL (
                    SELECT count(*)::int AS item_count
                    FROM quiz_items i
                    WHERE i.quiz_id = q.id
                ) qi ON TRUE
                LEFT JOIN LATERAL (
                    SELECT id, score, passed, grading, graded_at
                    FROM quiz_attempts a
                    WHERE a.quiz_id = q.id
                      AND a.user_id = :user_id
                      AND a.graded_at IS NOT NULL
                    ORDER BY a.id DESC
                    LIMIT 1
                ) qa ON TRUE
                WHERE q.id = :quiz_id
                  AND q.workspace_id = :workspace_id
                  AND q.user_id = :user_id
                  AND q.quiz_type = :quiz_type
                LIMIT 1
                """
            ),
            {
                "quiz_id": quiz_id,
                "workspace_id": workspace_id,
                "user_id": user_id,
                "quiz_type": quiz_type,
            },
        )
        .mappings()
        .first()
    )
