"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-11 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)

    op.create_table(
        "workspaces",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "trails",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("goal", sa.String(), nullable=False),
        sa.Column("target_depth", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "target_depth in ('remember', 'understand', 'apply', 'analyze', 'evaluate', 'create')",
            name="ck_trails_target_depth",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "concept_nodes",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("trail_id", uuid_type, nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("node_type", sa.String(), nullable=False),
        sa.Column("concept_level", sa.String(), nullable=False),
        sa.Column("difficulty", sa.String(), nullable=False),
        sa.Column("bloom_level", sa.String(), nullable=False),
        sa.Column(
            "mastery_check_labels",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.CheckConstraint(
            "node_type in ('concept', 'skill', 'misconception', 'example')",
            name="ck_concept_nodes_node_type",
        ),
        sa.CheckConstraint(
            "concept_level in ('umbrella', 'topic', 'subtopic', 'granular')",
            name="ck_concept_nodes_concept_level",
        ),
        sa.CheckConstraint(
            "difficulty in ('beginner', 'intermediate', 'advanced')",
            name="ck_concept_nodes_difficulty",
        ),
        sa.CheckConstraint(
            "bloom_level in ('remember', 'understand', 'apply', 'analyze', 'evaluate', 'create')",
            name="ck_concept_nodes_bloom_level",
        ),
        sa.ForeignKeyConstraint(["trail_id"], ["trails.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trail_id", "slug", name="uq_concept_nodes_trail_slug"),
    )
    op.create_table(
        "source_records",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("origin", sa.String(), nullable=False),
        sa.Column("access", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("license", sa.String(), nullable=True),
        sa.Column(
            "include_on_public_export",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("metadata_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.CheckConstraint(
            "origin in ('research_agent', 'user_upload', 'manual', 'system')",
            name="ck_source_records_origin",
        ),
        sa.CheckConstraint(
            "access in ('public', 'private', 'restricted', 'unknown')",
            name="ck_source_records_access",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "concept_edges",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("trail_id", uuid_type, nullable=False),
        sa.Column("source_node_id", uuid_type, nullable=False),
        sa.Column("target_node_id", uuid_type, nullable=False),
        sa.Column("relation_type", sa.String(), nullable=False),
        sa.CheckConstraint(
            "relation_type in ('prerequisite', 'contains', 'application', 'related')",
            name="ck_concept_edges_relation_type",
        ),
        sa.ForeignKeyConstraint(["source_node_id"], ["concept_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["concept_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trail_id"], ["trails.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "concept_source_links",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("concept_id", uuid_type, nullable=False),
        sa.Column("source_id", uuid_type, nullable=False),
        sa.Column("relation", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["concept_id"], ["concept_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["source_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("concept_source_links")
    op.drop_table("concept_edges")
    op.drop_table("source_records")
    op.drop_table("concept_nodes")
    op.drop_table("trails")
    op.drop_table("workspaces")
