"""Add concept_tier enum and tier column to concepts_canon.

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260301_0009"
down_revision = "20260301_0008"
branch_labels = None
depends_on = None

_ENUM_NAME = "concept_tier"
_ENUM_VALUES = ("umbrella", "topic", "subtopic", "granular")


def upgrade() -> None:
    concept_tier = postgresql.ENUM(*_ENUM_VALUES, name=_ENUM_NAME)
    concept_tier.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "concepts_canon",
        sa.Column("tier", sa.Enum(*_ENUM_VALUES, name=_ENUM_NAME), nullable=True),
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_concepts_canon_tier
            ON concepts_canon (workspace_id, tier)
            WHERE tier IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_concepts_canon_tier")
    op.drop_column("concepts_canon", "tier")
    op.execute("DROP TYPE IF EXISTS concept_tier")
