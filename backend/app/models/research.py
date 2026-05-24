import uuid

from sqlalchemy import JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDType, uuid_pk


class TrailResearchTrace(TimestampMixin, Base):
    __tablename__ = "trail_research_traces"
    __table_args__ = (
        UniqueConstraint("trail_id", name="uq_trail_research_traces_trail_id"),
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
    trace_json: Mapped[dict] = mapped_column(JSON, nullable=False)
