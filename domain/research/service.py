"""Research domain service – orchestration for research CRUD operations."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from adapters.db import research as research_db
from core.schemas.research import (
    ResearchCandidateSummary,
    ResearchRunSummary,
    ResearchSourceSummary,
)


class CandidateNotFoundError(Exception):
    """Raised when a candidate lookup fails."""


def _row_to_source(row: dict[str, Any]) -> ResearchSourceSummary:
    return ResearchSourceSummary(
        source_id=int(row["id"]),
        url=str(row["url"]),
        label=str(row["label"]) if row.get("label") else None,
        active=bool(row["active"]),
    )


def _row_to_run(row: dict[str, Any]) -> ResearchRunSummary:
    return ResearchRunSummary(
        run_id=int(row["id"]),
        status=str(row["status"]),
        candidates_found=int(row["candidates_found"]),
        started_at=row["started_at"],
        finished_at=row.get("finished_at"),
    )


def _row_to_candidate(row: dict[str, Any]) -> ResearchCandidateSummary:
    return ResearchCandidateSummary(
        candidate_id=int(row["id"]),
        source_url=str(row["source_url"]),
        title=str(row["title"]) if row.get("title") else None,
        snippet=str(row["snippet"]) if row.get("snippet") else None,
        status=str(row["status"]),
    )


# ── Sources ───────────────────────────────────────────────────────────


def add_source(
    db: Session,
    *,
    workspace_id: int,
    url: str,
    label: str | None,
) -> ResearchSourceSummary:
    """Register or reactivate a research source URL."""
    clean_url = url.strip()
    clean_label = (label or "").strip() or None
    row = research_db.upsert_source(
        db,
        workspace_id=workspace_id,
        url=clean_url,
        label=clean_label,
    )
    db.commit()
    return _row_to_source(row)


def list_sources(db: Session, *, workspace_id: int) -> list[ResearchSourceSummary]:
    """List all research sources for a workspace."""
    rows = research_db.list_sources(db, workspace_id=workspace_id)
    return [_row_to_source(r) for r in rows]


def deactivate_source(db: Session, *, source_id: int, workspace_id: int) -> None:
    """Soft-delete a research source."""
    research_db.deactivate_source(db, source_id=source_id, workspace_id=workspace_id)
    db.commit()


# ── Runs ──────────────────────────────────────────────────────────────


def trigger_run(db: Session, *, workspace_id: int) -> ResearchRunSummary:
    """Create a new research run."""
    row = research_db.insert_run(db, workspace_id=workspace_id)
    db.commit()
    return _row_to_run(row)


def list_runs(
    db: Session,
    *,
    workspace_id: int,
    limit: int = 10,
) -> list[ResearchRunSummary]:
    """List recent research runs."""
    rows = research_db.list_runs(db, workspace_id=workspace_id, limit=limit)
    return [_row_to_run(r) for r in rows]


# ── Candidates ────────────────────────────────────────────────────────


def list_candidates(
    db: Session,
    *,
    workspace_id: int,
    run_id: int | None = None,
    status_filter: str | None = None,
) -> list[ResearchCandidateSummary]:
    """List candidates, optionally filtered by run or status."""
    rows = research_db.list_candidates(
        db,
        workspace_id=workspace_id,
        run_id=run_id,
        status_filter=status_filter,
    )
    return [_row_to_candidate(r) for r in rows]


def review_candidate(
    db: Session,
    *,
    candidate_id: int,
    workspace_id: int,
    new_status: str,
    user_id: int,
) -> ResearchCandidateSummary:
    """Approve or reject a research candidate. Raises CandidateNotFoundError if missing."""
    row = research_db.review_candidate(
        db,
        candidate_id=candidate_id,
        workspace_id=workspace_id,
        new_status=new_status,
        user_id=user_id,
    )
    if row is None:
        raise CandidateNotFoundError
    db.commit()
    return _row_to_candidate(row)


# ── Topic / query planning (AR5.5) ───────────────────────────────────


def execute_topic_plan(
    db: Session,
    *,
    workspace_id: int,
    topic: str,
    subtopics: list[str] | None = None,
    source_classes: list[str] | None = None,
    rationale: str = "",
    priority: str = "medium",
) -> dict:
    """Build a query plan from an approved topic and enqueue candidates.

    Returns a dict with run_id, topic, queries_planned, candidates_inserted.
    """
    from domain.research.planner import TopicProposal
    from domain.research.query_planner import build_query_plan, enqueue_query_results

    # Create a research run for this planned execution
    run_row = research_db.insert_run(db, workspace_id=workspace_id)
    db.commit()
    run_id = int(run_row["id"])

    proposal = TopicProposal(
        topic=topic,
        subtopics=subtopics or [],
        source_classes=source_classes or [],
        rationale=rationale,
        priority=priority,
    )

    plan = build_query_plan(proposal=proposal)

    # Convert planned queries into candidate-shaped results
    results = [
        {
            "source_url": f"planned://{q.source_class}/{q.query_text[:200]}",
            "title": f"[Planned] {q.query_text[:200]}",
            "snippet": f"Source class: {q.source_class}, from topic: {topic}",
        }
        for q in plan.queries
    ]

    inserted = enqueue_query_results(
        db,
        workspace_id=workspace_id,
        run_id=run_id,
        results=results,
    )

    return {
        "run_id": run_id,
        "topic": plan.topic,
        "queries_planned": plan.query_count,
        "candidates_inserted": inserted,
    }


# ── Candidate promotion (AR5.6) ──────────────────────────────────────


def promote_reviewed_candidate(
    db: Session,
    *,
    candidate_id: int,
    workspace_id: int,
    user_id: int,
    has_quiz_gate: bool = False,
    quiz_passed: bool = False,
) -> dict:
    """Evaluate and optionally promote an approved candidate.

    Routes through evaluate_candidate_for_promotion() to enforce
    learning-gated promotion policy. Returns the decision and whether
    the candidate was actually promoted.
    """
    from domain.research.promotion import (
        evaluate_candidate_for_promotion,
        promote_candidate,
        record_promotion_feedback,
    )

    # Look up current candidate status
    rows = research_db.list_candidates(
        db,
        workspace_id=workspace_id,
        run_id=None,
        status_filter=None,
    )
    candidate_row = next(
        (r for r in rows if int(r["id"]) == candidate_id),
        None,
    )
    if candidate_row is None:
        raise CandidateNotFoundError

    decision = evaluate_candidate_for_promotion(
        candidate_id=candidate_id,
        candidate_status=str(candidate_row["status"]),
        has_quiz_gate=has_quiz_gate,
        quiz_passed=quiz_passed,
    )

    promoted = False
    if decision.action == "promote":
        promoted = promote_candidate(
            db,
            candidate_id=candidate_id,
            workspace_id=workspace_id,
            decision=decision,
        )

    record_promotion_feedback(
        db,
        candidate_id=candidate_id,
        workspace_id=workspace_id,
        user_id=user_id,
        feedback=f"Promotion decision: {decision.action} — {decision.reason}",
    )

    return {
        "candidate_id": candidate_id,
        "action": decision.action,
        "reason": decision.reason,
        "promoted": promoted,
    }
