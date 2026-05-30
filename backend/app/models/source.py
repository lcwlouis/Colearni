import os
import uuid

import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.orm import Mapped, attributes, mapped_column
from sqlalchemy.types import UserDefinedType

from .base import Base, TimestampMixin, UUIDType, uuid_pk

try:
    from pgvector.sqlalchemy import Vector as _Vector

    def _embedding_column(dim: int) -> Mapped[list[float] | None]:
        return mapped_column(_Vector(dim), nullable=True)

except ImportError:

    class _FallbackVector(UserDefinedType):
        """Minimal pgvector SQLAlchemy type used when pgvector is not installed."""

        cache_ok = True
        _string = String()

        def __init__(self, dim: int | None = None) -> None:
            super().__init__()
            self.dim = dim

        def get_col_spec(self, **_kw) -> str:
            if self.dim is None:
                return "VECTOR"
            return f"VECTOR({self.dim})"

        def bind_processor(self, dialect):
            def process(value):
                return self._to_db(value)

            return process

        def literal_processor(self, dialect):
            string_literal_processor = self._string._cached_literal_processor(dialect)
            if string_literal_processor is None:
                return None

            def process(value):
                return string_literal_processor(self._to_db(value))

            return process

        def result_processor(self, dialect, coltype):
            def process(value):
                if value is None or isinstance(value, list):
                    return value
                if isinstance(value, bytes):
                    value = value.decode()
                return [float(item) for item in value.strip("[]").split(",") if item]

            return process

        def _to_db(self, value):
            if value is None:
                return None
            if hasattr(value, "tolist"):
                value = value.tolist()
            values = list(value)
            if self.dim is not None and len(values) != self.dim:
                raise ValueError(f"expected {self.dim} dimensions, not {len(values)}")
            return "[" + ",".join(str(float(item)) for item in values) + "]"

        class comparator_factory(UserDefinedType.Comparator):
            def l2_distance(self, other):
                return self.op("<->", return_type=sa.Float)(other)

            def max_inner_product(self, other):
                return self.op("<#>", return_type=sa.Float)(other)

            def cosine_distance(self, other):
                return self.op("<=>", return_type=sa.Float)(other)

            def l1_distance(self, other):
                return self.op("<+>", return_type=sa.Float)(other)

    def _embedding_column(dim: int) -> Mapped[list[float] | None]:
        return mapped_column(_FallbackVector(dim), nullable=True)


_EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", "1536"))


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
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )


class SourceChunk(Base):
    __tablename__ = "source_chunks"

    id: Mapped[uuid.UUID] = uuid_pk()
    source_revision_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("source_revisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    line_start: Mapped[int] = mapped_column(Integer, nullable=False)
    line_end: Mapped[int] = mapped_column(Integer, nullable=False)
    section_heading: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding: Mapped[list[float] | None] = _embedding_column(_EMBEDDING_DIM)


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
