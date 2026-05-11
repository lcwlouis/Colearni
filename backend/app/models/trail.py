import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDType, uuid_pk


class Trail(TimestampMixin, Base):
    __tablename__ = "trails"
    __table_args__ = (
        CheckConstraint(
            "target_depth in ('remember', 'understand', 'apply', 'analyze', 'evaluate', 'create')",
            name="ck_trails_target_depth",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    topic: Mapped[str] = mapped_column(String, nullable=False)
    goal: Mapped[str] = mapped_column(String, nullable=False)
    target_depth: Mapped[str] = mapped_column(String, nullable=False)
