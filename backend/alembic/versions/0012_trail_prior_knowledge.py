"""add trails.prior_knowledge

Revision ID: 0012_trail_prior_knowledge
Revises: 0011_source_chunks
Create Date: 2026-05-29 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_trail_prior_knowledge"
down_revision: str | None = "0011_source_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("trails", sa.Column("prior_knowledge", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("trails", "prior_knowledge")
