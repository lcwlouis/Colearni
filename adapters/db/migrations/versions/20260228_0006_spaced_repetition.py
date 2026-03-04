"""Add interval_days to practice_flashcard_progress for spaced repetition.

Revision ID: 20260228_0006
Revises: 20260227_0005
Create Date: 2026-02-28 00:00:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260228_0006"
down_revision: str = "20260227_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Add interval_days FLOAT column (default 1.0) to practice_flashcard_progress."""
    op.add_column(
        "practice_flashcard_progress",
        sa.Column(
            "interval_days",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
    )


def downgrade() -> None:
    """Remove interval_days column from practice_flashcard_progress."""
    op.drop_column("practice_flashcard_progress", "interval_days")
