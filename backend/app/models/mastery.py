import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base, UUIDType, uuid_pk


class MasteryRecord(Base):
    __tablename__ = "mastery_records"
    __table_args__ = (
        UniqueConstraint("workspace_id", "concept_id", name="uq_mastery_records_workspace_concept"),
        CheckConstraint(
            "status in ('not_started', 'learning', 'needs_review', 'mastered')",
            name="ck_mastery_records_status",
        ),
        CheckConstraint(
            "bloom_level in ('remember', 'understand', 'apply', 'analyze', 'evaluate', 'create')",
            name="ck_mastery_records_bloom_level",
        ),
        CheckConstraint(
            "score >= 0.0 AND score <= 1.0",
            name="ck_mastery_records_score_range",
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
    status: Mapped[str] = mapped_column(String, nullable=False)
    bloom_level: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default=text("0"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        CheckConstraint(
            "quiz_type in ('level_up', 'practice')",
            name="ck_quiz_attempts_quiz_type",
        ),
        CheckConstraint(
            "score >= 0.0 AND score <= 1.0",
            name="ck_quiz_attempts_score_range",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("concept_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    quiz_type: Mapped[str] = mapped_column(String, nullable=False)
    questions_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    answers_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    evaluator_feedback: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class QuizDraft(Base):
    __tablename__ = "quiz_drafts"
    __table_args__ = (
        UniqueConstraint("concept_id", "quiz_type", name="uq_quiz_drafts_concept_type"),
        CheckConstraint(
            "quiz_type in ('level_up', 'practice')",
            name="ck_quiz_drafts_quiz_type",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("concept_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    quiz_type: Mapped[str] = mapped_column(String, nullable=False)
    questions_json: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
