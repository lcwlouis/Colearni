"""add structured conversation reasoning parts

Revision ID: 0007_reasoning_parts
Revises: 0006_quiz_drafts
Create Date: 2026-05-22 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_reasoning_parts"
down_revision: str | None = "0006_quiz_drafts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversation_turns", sa.Column("reasoning_parts", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("conversation_turns", "reasoning_parts")
