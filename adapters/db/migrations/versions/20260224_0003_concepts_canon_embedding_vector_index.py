"""Add ivfflat cosine index for canonical concept embeddings.

Revision ID: 20260224_0003
Revises: 20260224_0002
Create Date: 2026-02-24 09:30:00
"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260224_0003"
down_revision: str | None = "20260224_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create ivfflat vector index for canonical concept retrieval."""
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_concepts_canon_embedding_ivfflat_cosine "
        "ON concepts_canon USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    """Drop ivfflat vector index for canonical concept retrieval."""
    op.execute("DROP INDEX IF EXISTS ix_concepts_canon_embedding_ivfflat_cosine")
