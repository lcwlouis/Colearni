from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base, UUIDType, uuid_pk


class Artifact(Base):
    """A persisted, validated learning artifact.

    Artifacts are BOTH trail-attached (``trail_id``, required) and optionally
    concept-attached (``concept_id``, nullable). ``artifact_type`` is the
    discriminator and equals the envelope ``kind``. ``payload_json`` stores the
    full validated envelope dict (mirroring how ``QuizDraft`` stores questions).
    """

    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint(
            "artifact_type in ('worked_example', 'comparison_card', 'timeline', "
            "'mini_graph', 'simulation_slider')",
            name="ck_artifacts_artifact_type",
        ),
        CheckConstraint(
            "visibility in ('local_only', 'source_derived')",
            name="ck_artifacts_visibility",
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
    concept_id: Mapped[uuid.UUID | None] = mapped_column(
        UUIDType(),
        ForeignKey("concept_nodes.id", ondelete="CASCADE"),
        nullable=True,
    )
    artifact_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_refs_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    visibility: Mapped[str] = mapped_column(String, nullable=False)
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
