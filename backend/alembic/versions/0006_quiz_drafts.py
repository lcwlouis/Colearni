"""add quiz drafts

Revision ID: 0006_quiz_drafts
Revises: 0005_conversation_tool_turns
Create Date: 2026-05-21 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_quiz_drafts"
down_revision: str | None = "0005_conversation_tool_turns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)

    op.create_table(
        "quiz_drafts",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("concept_id", uuid_type, nullable=False),
        sa.Column("quiz_type", sa.String(), nullable=False),
        sa.Column("questions_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quiz_type in ('level_up', 'practice')",
            name="ck_quiz_drafts_quiz_type",
        ),
        sa.ForeignKeyConstraint(["concept_id"], ["concept_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("concept_id", "quiz_type", name="uq_quiz_drafts_concept_type"),
    )


def downgrade() -> None:
    op.drop_table("quiz_drafts")
