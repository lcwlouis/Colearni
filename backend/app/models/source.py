import uuid

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDType, uuid_pk


class SourceRecord(Base):
    __tablename__ = "source_records"
    __table_args__ = (
        CheckConstraint(
            "origin in ('research_agent', 'user_upload', 'manual', 'system')",
            name="ck_source_records_origin",
        ),
        CheckConstraint(
            "access in ('public', 'private', 'restricted', 'unknown')",
            name="ck_source_records_access",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    origin: Mapped[str] = mapped_column(String, nullable=False)
    access: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    license: Mapped[str | None] = mapped_column(String, nullable=True)
    include_on_public_export: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )


class ConceptSourceLink(Base):
    __tablename__ = "concept_source_links"

    id: Mapped[uuid.UUID] = uuid_pk()
    concept_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("concept_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("source_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation: Mapped[str] = mapped_column(String, nullable=False)
