from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base, UUIDType, uuid_pk


class QuizAttemptSummary(Base):
    """Bounded, immutable summary derived from one immutable quiz attempt."""

    __tablename__ = "quiz_attempt_summaries"
    __table_args__ = (
        UniqueConstraint("quiz_attempt_id", name="uq_quiz_attempt_summaries_attempt"),
        CheckConstraint(
            "quiz_type in ('level_up', 'practice')",
            name="ck_quiz_attempt_summaries_quiz_type",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("concept_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    quiz_attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"),
        nullable=False,
    )
    quiz_type: Mapped[str] = mapped_column(String, nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    strengths_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    gaps_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    question_fingerprints_json: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class LearnerState(Base):
    """Mutable current learner state for one workspace-scoped concept."""

    __tablename__ = "learner_states"
    __table_args__ = (
        UniqueConstraint("workspace_id", "concept_id", name="uq_learner_states_workspace_concept"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("concept_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    strengths_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    misconceptions_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    next_repair_targets_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    last_quiz_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(),
        ForeignKey("quiz_attempts.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
