import uuid

from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDType, uuid_pk


class ConceptNode(Base):
    __tablename__ = "concept_nodes"
    __table_args__ = (
        UniqueConstraint("trail_id", "slug", name="uq_concept_nodes_trail_slug"),
        CheckConstraint(
            "node_type in ('concept', 'skill', 'misconception', 'example')",
            name="ck_concept_nodes_node_type",
        ),
        CheckConstraint(
            "concept_level in ('umbrella', 'topic', 'subtopic', 'granular')",
            name="ck_concept_nodes_concept_level",
        ),
        CheckConstraint(
            "difficulty in ('beginner', 'intermediate', 'advanced')",
            name="ck_concept_nodes_difficulty",
        ),
        CheckConstraint(
            "bloom_level in ('remember', 'understand', 'apply', 'analyze', 'evaluate', 'create')",
            name="ck_concept_nodes_bloom_level",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    trail_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("trails.id", ondelete="CASCADE"),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    node_type: Mapped[str] = mapped_column(String, nullable=False)
    concept_level: Mapped[str] = mapped_column(String, nullable=False)
    difficulty: Mapped[str] = mapped_column(String, nullable=False)
    bloom_level: Mapped[str] = mapped_column(String, nullable=False)
    mastery_check_labels: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )


class ConceptEdge(Base):
    __tablename__ = "concept_edges"
    __table_args__ = (
        CheckConstraint(
            "relation_type in ('prerequisite', 'contains', 'application', 'related')",
            name="ck_concept_edges_relation_type",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    trail_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("trails.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("concept_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType(),
        ForeignKey("concept_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type: Mapped[str] = mapped_column(String, nullable=False)
