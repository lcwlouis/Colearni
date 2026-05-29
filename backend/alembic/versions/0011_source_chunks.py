"""add source chunks

Revision ID: 0011_source_chunks
Revises: 0010_link_unique
Create Date: 2026-05-25 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import exc
from sqlalchemy.dialects import postgresql

from backend.app.settings import settings

revision: str = "0011_source_chunks"
down_revision: str | None = "0010_link_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    uuid_type = postgresql.UUID(as_uuid=True)

    op.add_column("source_revisions", sa.Column("raw_text", sa.Text(), nullable=True))
    op.create_table(
        "source_chunks",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("source_revision_id", uuid_type, nullable=False),
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("section_heading", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_revision_id"], ["source_revisions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_source_chunks_source_revision_id",
        "source_chunks",
        ["source_revision_id"],
    )
    op.create_index("ix_source_chunks_workspace_id", "source_chunks", ["workspace_id"])
    _add_embedding_column(is_postgres)


def downgrade() -> None:
    op.drop_table("source_chunks")
    op.drop_column("source_revisions", "raw_text")


def _add_embedding_column(is_postgres: bool) -> None:
    if not is_postgres:
        op.add_column("source_chunks", sa.Column("embedding", sa.JSON(), nullable=True))
        return

    bind = op.get_bind()
    try:
        with bind.begin_nested():
            op.execute("CREATE EXTENSION IF NOT EXISTS vector")
            # Match the configured embedding dimension so the column lines up with
            # EmbeddingClient output (and the ORM column derived from EMBEDDING_DIM).
            op.execute(
                f"ALTER TABLE source_chunks ADD COLUMN embedding vector({settings.embedding_dim})"
            )
    except exc.SQLAlchemyError:
        op.add_column("source_chunks", sa.Column("embedding", sa.JSON(), nullable=True))
