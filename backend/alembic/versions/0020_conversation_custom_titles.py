"""add custom titles for conversation threads

Revision ID: 0020_conversation_custom_titles
Revises: 0019_notes
Create Date: 2026-06-01 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_conversation_custom_titles"
down_revision: str | None = "0019_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("custom_title", sa.String(length=120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "custom_title")
