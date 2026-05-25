import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.orm import Mapped, attributes, mapped_column

from .base import Base, TimestampMixin, UUIDType, uuid_pk


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


class SourceRevision(TimestampMixin, Base):
    __tablename__ = "source_revisions"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending_parse', 'parsed', 'failed', 'skipped')",
            name="ck_source_revisions_status",
        ),
        UniqueConstraint("source_id", "revision_number", name="uq_source_revisions_number"),
        UniqueConstraint("workspace_id", "object_key", name="uq_source_revisions_object_key"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("source_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    parser_name: Mapped[str] = mapped_column(String, nullable=False)
    parser_version: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )


SOURCE_REVISION_IDENTITY_FIELDS = {
    "object_key",
    "content_hash",
    "revision_number",
    "source_id",
    "workspace_id",
}


@event.listens_for(SourceRevision, "before_update")
def _prevent_source_revision_identity_updates(mapper, _connection, target: SourceRevision) -> None:
    changed_identity_fields = [
        attr.key
        for attr in mapper.attrs
        if attr.key in SOURCE_REVISION_IDENTITY_FIELDS
        and attributes.get_history(target, attr.key).has_changes()
    ]
    if changed_identity_fields:
        fields = ", ".join(sorted(changed_identity_fields))
        raise ValueError(f"SourceRevision identity fields are immutable: {fields}")


class ConceptSourceLink(Base):
    __tablename__ = "concept_source_links"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "concept_id",
            "relation",
            name="uq_concept_source_links_source_concept_relation",
        ),
    )

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
