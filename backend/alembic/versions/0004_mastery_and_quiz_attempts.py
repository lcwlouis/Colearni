"""add mastery and quiz attempts

Revision ID: 0004_mastery_and_quiz_attempts
Revises: 0003_conversation_turn_reasoning
Create Date: 2026-05-19 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_mastery_and_quiz_attempts"
down_revision: str | None = "0003_conversation_turn_reasoning"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)

    op.create_table(
        "mastery_records",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("concept_id", uuid_type, nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("bloom_level", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status in ('not_started', 'learning', 'needs_review', 'mastered')",
            name="ck_mastery_records_status",
        ),
        sa.CheckConstraint(
            "bloom_level in ('remember', 'understand', 'apply', 'analyze', 'evaluate', 'create')",
            name="ck_mastery_records_bloom_level",
        ),
        sa.CheckConstraint(
            "score >= 0.0 AND score <= 1.0",
            name="ck_mastery_records_score_range",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["concept_id"], ["concept_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "concept_id",
            name="uq_mastery_records_workspace_concept",
        ),
    )

    op.create_table(
        "quiz_attempts",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("concept_id", uuid_type, nullable=False),
        sa.Column("quiz_type", sa.String(), nullable=False),
        sa.Column("questions_json", sa.JSON(), nullable=False),
        sa.Column("answers_json", sa.JSON(), nullable=False),
        sa.Column("evaluator_feedback", sa.Text(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quiz_type in ('level_up', 'practice')",
            name="ck_quiz_attempts_quiz_type",
        ),
        sa.CheckConstraint(
            "score >= 0.0 AND score <= 1.0",
            name="ck_quiz_attempts_score_range",
        ),
        sa.ForeignKeyConstraint(["concept_id"], ["concept_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("quiz_attempts")
    op.drop_table("mastery_records")
