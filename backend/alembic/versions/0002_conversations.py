"""add conversations tables

Revision ID: 0002_conversations
Revises: 0001_initial
Create Date: 2026-05-18 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_conversations"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)

    op.create_table(
        "conversations",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("trail_id", uuid_type, nullable=False),
        sa.Column("concept_id", uuid_type, nullable=False),
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
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trail_id"], ["trails.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["concept_id"], ["concept_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "trail_id",
            "concept_id",
            name="uq_conversations_workspace_trail_concept",
        ),
    )
    op.create_table(
        "conversation_turns",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("conversation_id", uuid_type, nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(), nullable=True),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role in ('user', 'assistant')",
            name="ck_conversation_turns_role",
        ),
        sa.CheckConstraint(
            "mode IS NULL OR mode in ('socratic', 'direct', 'repair', 'quiz_prompt', 'explore')",
            name="ck_conversation_turns_mode",
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "turn_index",
            name="uq_conversation_turns_index",
        ),
    )
    op.create_table(
        "conversation_summaries",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("conversation_id", uuid_type, nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("turns_covered_to", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("conversation_summaries")
    op.drop_table("conversation_turns")
    op.drop_table("conversations")
