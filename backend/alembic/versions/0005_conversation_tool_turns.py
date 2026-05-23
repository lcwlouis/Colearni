"""add conversation tool turn support

Revision ID: 0005_conversation_tool_turns
Revises: 0004_mastery_and_quiz_attempts
Create Date: 2026-05-19 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_conversation_tool_turns"
down_revision: str | None = "0004_mastery_and_quiz_attempts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversation_turns",
        sa.Column("kind", sa.String(), nullable=False, server_default="visible"),
    )

    op.drop_constraint("ck_conversation_turns_role", "conversation_turns", type_="check")
    op.create_check_constraint(
        "ck_conversation_turns_role",
        "conversation_turns",
        "role in ('user', 'assistant', 'tool')",
    )

    op.create_check_constraint(
        "ck_conversation_turns_kind",
        "conversation_turns",
        "kind in ('visible', 'tool_call', 'tool_result')",
    )

    op.drop_constraint("ck_conversation_turns_mode", "conversation_turns", type_="check")
    op.create_check_constraint(
        "ck_conversation_turns_mode",
        "conversation_turns",
        "mode IS NULL OR mode in ('socratic', 'direct', 'repair', 'quiz_prompt', 'explore', 'free_explore')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_conversation_turns_mode", "conversation_turns", type_="check")
    op.create_check_constraint(
        "ck_conversation_turns_mode",
        "conversation_turns",
        "mode IS NULL OR mode in ('socratic', 'direct', 'repair', 'quiz_prompt', 'explore')",
    )

    op.drop_constraint("ck_conversation_turns_kind", "conversation_turns", type_="check")

    op.drop_constraint("ck_conversation_turns_role", "conversation_turns", type_="check")
    op.create_check_constraint(
        "ck_conversation_turns_role",
        "conversation_turns",
        "role in ('user', 'assistant')",
    )

    op.drop_column("conversation_turns", "kind")
