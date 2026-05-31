from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base, UUIDType, uuid_pk


class Pin(Base):
    """A polymorphic "saved"/"pinned" reference, scoped to workspace + trail.

    ``item_type`` discriminates the referenced item (``artifact``,
    ``quiz_attempt`` or ``flashcard`` — a flashcard deck id); ``item_id`` is the
    referenced row's id. The unique
    constraint on ``(workspace_id, trail_id, item_type, item_id)`` makes pinning
    IDEMPOTENT (a second pin of the same item is a no-op). Per-USER == per-
    workspace for now (becomes user-scoped when auth lands).
    """

    __tablename__ = "pins"
    __table_args__ = (
        CheckConstraint(
            "item_type in ('artifact', 'quiz_attempt', 'flashcard', 'concept')",
            name="ck_pins_item_type",
        ),
        UniqueConstraint(
            "workspace_id",
            "trail_id",
            "item_type",
            "item_id",
            name="uq_pins_workspace_trail_item",
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
    item_type: Mapped[str] = mapped_column(String, nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(UUIDType(), nullable=False)
    pinned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
