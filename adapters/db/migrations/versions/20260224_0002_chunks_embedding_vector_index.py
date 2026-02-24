"""Add ivfflat cosine index for chunk embedding retrieval.

Revision ID: 20260224_0002
Revises: 20260224_0001
Create Date: 2026-02-24 02:10:00
"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260224_0002"
down_revision: str | None = "20260224_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create ivfflat vector index for chunk retrieval."""
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_ivfflat_cosine "
        "ON chunks USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    """Drop ivfflat vector index for chunk retrieval."""
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_ivfflat_cosine")
