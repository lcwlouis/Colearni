import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDType, uuid_pk


class Conversation(Base):
    """One active conversation thread per (workspace, trail, concept) triple."""

    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "trail_id",
            "concept_id",
            name="uq_conversations_workspace_trail_concept",
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
    # updated_at is set explicitly by the service layer; no onupdate hook.
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


class ConversationTurn(Base):
    """A single user or assistant turn within a conversation."""

    __tablename__ = "conversation_turns"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "turn_index",
            name="uq_conversation_turns_index",
        ),
        CheckConstraint(
            "role in ('user', 'assistant')",
            name="ck_conversation_turns_role",
        ),
        CheckConstraint(
            "mode IS NULL OR mode in ('socratic', 'direct', 'repair', 'quiz_prompt', 'explore')",
            name="ck_conversation_turns_mode",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional provider-exposed thinking text used to rehydrate reasoning traces.
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str | None] = mapped_column(String, nullable=True)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ConversationSummary(Base):
    """A rolling summary produced after a batch of turns to keep context windows bounded."""

    __tablename__ = "conversation_summaries"

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    turns_covered_to: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
