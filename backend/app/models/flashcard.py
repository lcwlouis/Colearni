from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base, UUIDType, uuid_pk


class FlashcardDeck(Base):
    """A per-concept deck of flashcards.

    Flashcards are a DEDICATED subsystem (not a generic artifact). Each concept
    owns at most one deck (the unique constraint on ``(workspace_id,
    concept_id)`` enforces this); the deck is the retrievable/pinnable unit, like
    a quiz attempt. The canonical store is relational — CSV/JSON are export only.
    """

    __tablename__ = "flashcard_decks"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "concept_id",
            name="uq_flashcard_decks_workspace_concept",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    trail_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("trails.id", ondelete="CASCADE"),
        nullable=False,
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("concept_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
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


class Flashcard(Base):
    """A single atomic flashcard with Leitner/FSRS-ready scheduling state.

    Scheduling v1 is LEITNER (the ``box`` + geometric ``interval_days``); the
    extra columns (``last_reviewed``, ``due``, ``reps``, ``lapses``) keep the
    schema FSRS-ready without committing to FSRS logic in v1.
    """

    __tablename__ = "flashcards"
    __table_args__ = (
        CheckConstraint(
            "card_type in ('basic', 'cloze', 'reverse')",
            name="ck_flashcards_card_type",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    deck_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("flashcard_decks.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    front: Mapped[str] = mapped_column(String, nullable=False)
    back: Mapped[str] = mapped_column(String, nullable=False)
    hint: Mapped[str | None] = mapped_column(String, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    card_type: Mapped[str] = mapped_column(String, nullable=False, default="basic")

    # Scheduling state (Leitner v1; FSRS-ready).
    box: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_reviewed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lapses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
