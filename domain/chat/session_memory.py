"""Chat session persistence and context compaction helpers."""

from __future__ import annotations

import logging
from typing import Any

from adapters.db.chat import (
    append_chat_message,
    assert_chat_session,
    count_chat_messages,
    latest_system_summary,
    list_recent_chat_messages,
    set_chat_session_title_if_missing,
)
from domain.chat.title_gen import generate_session_title
from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger("domain.chat.session_memory")

COMPACTION_THRESHOLD = 40
COMPACTION_KEEP_RECENT = 16
SUMMARY_SOURCE_LIMIT = 24
ASSESSMENT_CARD_LIMIT = 5
FLASHCARD_PROGRESS_LIMIT = 10
QUIZ_PROGRESS_LIMIT = 8


def load_history_text(
    session: Session,
    *,
    session_id: int | None,
) -> str:
    """Load chat history as labeled sections for the tutor prompt.

    Returns a structured string with COMPACTED PRIOR CONTEXT and
    RECENT CHAT HISTORY sections when data exists.
    """
    if session_id is None:
        return ""

    summary = latest_system_summary(session, session_id=session_id) or ""
    recent = list_recent_chat_messages(session, session_id=session_id, limit=10)

    sections: list[str] = []

    if summary:
        sections.append(f"COMPACTED PRIOR CONTEXT:\n{summary}")

    recent_lines: list[str] = []
    for message in recent:
        payload = message.get("payload") if isinstance(message, dict) else {}
        if not isinstance(payload, dict):
            continue
        text_value = str(payload.get("text", "")).strip()
        if not text_value:
            continue
        role = str(message.get("type", ""))
        if role == "user":
            recent_lines.append(f"User: {text_value}")
        elif role == "assistant":
            recent_lines.append(f"Tutor: {text_value}")

    if recent_lines:
        sections.append("RECENT CHAT HISTORY:\n" + "\n".join(recent_lines))

    return "\n\n".join(sections)


def persist_turn(
    session: Session,
    *,
    workspace_id: int,
    session_id: int | None,
    user_id: int | None,
    user_text: str,
    assistant_payload: dict[str, Any],
    concept_name: str | None = None,
    session_concept_name: str | None = None,
    settings: Any | None = None,
) -> None:
    if session_id is None:
        return
    if user_id is None:
        return

    assert_chat_session(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    append_chat_message(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        user_id=user_id,
        message_type="user",
        payload={"text": user_text.strip()},
    )
    append_chat_message(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        user_id=user_id,
        message_type="assistant",
        payload=assistant_payload,
    )
    set_chat_session_title_if_missing(
        session,
        session_id=session_id,
        title=generate_session_title(
            user_query=user_text,
            concept_name=concept_name,
            session_concept_name=session_concept_name,
        ),
    )
    maybe_compact_session_context(
        session,
        workspace_id=workspace_id,
        session_id=session_id,
        user_id=user_id,
        settings=settings,
    )
    session.commit()


def maybe_compact_session_context(
    session: Session,
    *,
    workspace_id: int,
    session_id: int,
    user_id: int,
    threshold: int = COMPACTION_THRESHOLD,
    keep_recent: int = COMPACTION_KEEP_RECENT,
    settings: Any | None = None,
) -> None:
    total = count_chat_messages(session, session_id=session_id)
    if total <= threshold:
        return

    recent = list_recent_chat_messages(session, session_id=session_id, limit=keep_recent)
    if len(recent) >= total:
        return

    source = list_recent_chat_messages(
        session,
        session_id=session_id,
        limit=min(SUMMARY_SOURCE_LIMIT, total - keep_recent),
    )
    lines: list[str] = []
    for item in source:
        payload = item.get("payload") if isinstance(item, dict) else {}
        if not isinstance(payload, dict):
            continue
        text_value = str(payload.get("text", "")).strip()
        if not text_value:
            continue
        role = str(item.get("type", ""))
        if role == "user":
            lines.append(f"User: {text_value}")
        elif role == "assistant":
            lines.append(f"Tutor: {text_value}")

    if not lines:
        return

    raw_summary = "\n".join(lines)

    # Try LLM summarization if settings available and content is long enough
    summary = raw_summary
    if settings is not None and len(raw_summary) > 800:
        try:
            from domain.chat.response_service import build_tutor_llm_client

            llm_client = build_tutor_llm_client(settings=settings)
            if llm_client is not None:
                compaction_prompt = (
                    "Summarize the following tutor-learner conversation concisely. "
                    "Preserve key topics discussed, questions asked, misconceptions identified, "
                    "and learning progress. Keep the summary under 200 words.\n\n"
                    f"CONVERSATION:\n{raw_summary}"
                )
                summary = llm_client.generate_tutor_text(
                    prompt=compaction_prompt,
                    system_prompt="You are a conversation summarizer. Return only the summary, nothing else.",
                ).strip()
                if not summary:
                    summary = raw_summary
        except Exception:
            log.debug("LLM compaction failed, using raw summary")
            summary = raw_summary

    append_chat_message(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        user_id=user_id,
        message_type="system",
        payload={
            "summary": summary,
            "kind": "context_compaction",
            "source_count": len(lines),
        },
    )


def load_chat_context_for_quiz(
    session: Session,
    *,
    session_id: int | None,
    max_turns: int = 8,
) -> str:
    """Load condensed chat history for inclusion in quiz generation prompts.

    Extracts recent user/tutor exchanges so the quiz generator can target
    areas the learner discussed, struggled with, or showed curiosity about.
    Returns a compact string; empty if no usable history.
    """
    if session_id is None:
        return ""

    recent = list_recent_chat_messages(session, session_id=session_id, limit=max_turns * 2)
    lines: list[str] = []
    for message in recent:
        if not isinstance(message, dict):
            continue
        payload = message.get("payload")
        if not isinstance(payload, dict):
            continue
        text_value = str(payload.get("text", "")).strip()
        if not text_value:
            continue
        role = str(message.get("type", ""))
        if role == "user":
            lines.append(f"Learner: {text_value}")
        elif role == "assistant":
            lines.append(f"Tutor: {text_value}")
        if len(lines) >= max_turns:
            break

    if not lines:
        return ""

    return "\n".join(lines)


__all__ = [
    "load_assessment_context",
    "load_chat_context_for_quiz",
    "load_flashcard_progress",
    "load_quiz_progress_snapshot",
    "load_history_text",
    "maybe_compact_session_context",
    "persist_assessment_card",
    "persist_turn",
]


# ── Slice 7: Assessment card persistence ──────────────────────────────


def persist_assessment_card(
    session: Session,
    *,
    workspace_id: int,
    session_id: int | None,
    user_id: int | None,
    card_payload: dict[str, Any],
) -> None:
    """Persist a quiz/practice result as a structured 'card' message."""
    if session_id is None or user_id is None:
        return
    assert_chat_session(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        user_id=user_id,
    )
    append_chat_message(
        session,
        session_id=session_id,
        workspace_id=workspace_id,
        user_id=user_id,
        message_type="card",
        payload=card_payload,
    )
    session.commit()


# ── Slice 8: Assessment history for tutor prompt context ──────────────


def load_assessment_context(
    session: Session,
    *,
    session_id: int | None,
) -> str:
    """Load recent assessment cards from the session to include in tutor prompt.

    Returns a formatted string summarizing recent quiz/practice results.
    """
    if session_id is None:
        return ""

    recent = list_recent_chat_messages(session, session_id=session_id, limit=50)
    cards: list[dict[str, Any]] = []
    for message in recent:
        if not isinstance(message, dict):
            continue
        if message.get("type") != "card":
            continue
        payload = message.get("payload")
        if isinstance(payload, dict) and payload.get("card_type") in (
            "quiz_result",
            "practice_result",
        ):
            cards.append(payload)
        if len(cards) >= ASSESSMENT_CARD_LIMIT:
            break

    if not cards:
        return ""

    lines: list[str] = []
    for card in cards:
        concept = card.get("concept_name", "unknown")
        score = card.get("score", 0)
        passed = "passed" if card.get("passed") else "not passed"
        summary = card.get("summary", "")
        lines.append(
            f"- {card.get('card_type', 'result')}: {concept} "
            f"— score {score:.0%}, {passed}. {summary}"
        )
    return "\n".join(lines)


# ── S45: Flashcard progress snapshot for tutor context ────────────────


def load_flashcard_progress(
    session: Session,
    *,
    workspace_id: int,
    user_id: int | None,
    concept_id: int | None = None,
) -> str:
    """Load recent flashcard progress for inclusion in tutor prompt context.

    Returns a formatted FLASHCARD PROGRESS SNAPSHOT section.
    Scoped to concept if provided, otherwise workspace-wide.
    """
    if user_id is None:
        return ""

    try:
        params: dict[str, object] = {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "limit": FLASHCARD_PROGRESS_LIMIT,
        }
        concept_filter = ""
        if concept_id is not None:
            concept_filter = "AND fb.concept_id = :concept_id"
            params["concept_id"] = concept_id

        rows = (
            session.execute(
                text(f"""
                    SELECT
                        fb.concept_id,
                        cc.canonical_name,
                        fb.front,
                        fp.self_rating,
                        fp.passed,
                        fp.updated_at
                    FROM practice_flashcard_progress fp
                    JOIN practice_flashcard_bank fb
                        ON fb.id = fp.flashcard_id
                        AND fb.workspace_id = :workspace_id
                    LEFT JOIN concepts_canon cc
                        ON cc.id = fb.concept_id
                        AND cc.workspace_id = :workspace_id
                    WHERE fp.user_id = :user_id
                      {concept_filter}
                    ORDER BY fp.updated_at DESC
                    LIMIT :limit
                """),
                params,
            )
            .mappings()
            .all()
        )
    except Exception:
        if callable(getattr(session, "rollback", None)):
            session.rollback()
        return ""

    if not rows:
        return ""

    lines: list[str] = ["FLASHCARD PROGRESS SNAPSHOT:"]
    for row in rows:
        concept_name = str(row.get("canonical_name") or "unknown")
        front_text = str(row.get("front") or "")
        if len(front_text) > 80:
            front_text = front_text[:77] + "..."
        rating = str(row.get("self_rating") or "unrated")
        passed = "passed" if row.get("passed") else "in progress"
        updated = row.get("updated_at")
        date_str = ""
        if updated is not None:
            try:
                date_str = f", reviewed {updated.strftime('%Y-%m-%d')}"
            except Exception:  # noqa: BLE001
                pass
        card_label = f' "{front_text}"' if front_text else ""
        lines.append(f"- {concept_name}:{card_label} — {rating} ({passed}){date_str}")
    return "\n".join(lines)


def load_quiz_progress_snapshot(
    session: Session,
    *,
    workspace_id: int,
    user_id: int | None,
    concept_id: int | None = None,
) -> str:
    """Load recent level-up/practice quiz outcomes for tutor prompt context.

    Returns a bounded QUIZ PROGRESS SNAPSHOT section, scoped to concept when provided.
    """
    if user_id is None:
        return ""

    try:
        params: dict[str, object] = {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "limit": QUIZ_PROGRESS_LIMIT,
        }
        concept_filter = ""
        if concept_id is not None:
            concept_filter = "AND q.concept_id = :concept_id"
            params["concept_id"] = concept_id

        rows = (
            session.execute(
                text(
                    f"""
                    SELECT
                        q.quiz_type,
                        q.status,
                        cc.canonical_name AS concept_name,
                        q.created_at,
                        qa.score,
                        qa.passed,
                        qa.graded_at,
                        (SELECT COUNT(*) FROM quiz_items qi WHERE qi.quiz_id = q.id) AS item_count
                    FROM quizzes q
                    LEFT JOIN concepts_canon cc
                      ON cc.id = q.concept_id
                     AND cc.workspace_id = q.workspace_id
                    LEFT JOIN LATERAL (
                        SELECT score, passed, graded_at
                        FROM quiz_attempts a
                        WHERE a.quiz_id = q.id
                          AND a.user_id = :user_id
                          AND a.graded_at IS NOT NULL
                        ORDER BY a.id DESC
                        LIMIT 1
                    ) qa ON TRUE
                    WHERE q.workspace_id = :workspace_id
                      AND q.user_id = :user_id
                      AND q.quiz_type IN ('level_up', 'practice')
                      {concept_filter}
                    ORDER BY COALESCE(qa.graded_at, q.created_at) DESC, q.id DESC
                    LIMIT :limit
                    """
                ),
                params,
            )
            .mappings()
            .all()
        )
    except Exception:
        if callable(getattr(session, "rollback", None)):
            session.rollback()
        return ""

    if not rows:
        return ""

    lines: list[str] = ["QUIZ PROGRESS SNAPSHOT:"]
    for row in rows:
        quiz_type = str(row.get("quiz_type") or "quiz")
        concept_name = str(row.get("concept_name") or "unknown")
        item_count = row.get("item_count") or 0
        items_label = f", {item_count} questions" if item_count else ""
        # Determine date from graded_at or created_at
        quiz_date = row.get("graded_at") or row.get("created_at")
        date_str = ""
        if quiz_date is not None:
            try:
                date_str = f", {quiz_date.strftime('%Y-%m-%d')}"
            except Exception:  # noqa: BLE001
                pass
        if row.get("score") is not None:
            score = float(row.get("score") or 0.0)
            passed = "passed" if row.get("passed") else "not passed"
            lines.append(f"- {quiz_type} {concept_name}: score {score:.0%}, {passed}{items_label}{date_str}")
        else:
            status = str(row.get("status") or "ready")
            lines.append(f"- {quiz_type} {concept_name}: status {status}{items_label}{date_str}")
    return "\n".join(lines)
