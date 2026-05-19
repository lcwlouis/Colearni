"""add reasoning to conversation turns

Revision ID: 0003_conversation_turn_reasoning
Revises: 0002_conversations
Create Date: 2026-05-19 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_conversation_turn_reasoning"
down_revision: str | None = "0002_conversations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversation_turns", sa.Column("reasoning", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("conversation_turns", "reasoning")
