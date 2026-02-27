"""Add summary column to documents table.

Revision ID: 20260227_0005
Revises: 20260227_0004
Create Date: 2026-02-27 12:00:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260227_0005"
down_revision: str = "20260227_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Add summary TEXT column to documents table."""
    op.add_column(
        "documents",
        sa.Column("summary", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove summary column from documents table."""
    op.drop_column("documents", "summary")
