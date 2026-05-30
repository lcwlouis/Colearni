"""add learner state and quiz attempt summaries

Revision ID: 0013_learner_state
Revises: 0012_trail_prior_knowledge
Create Date: 2026-05-30 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_learner_state"
down_revision: str | None = "0012_trail_prior_knowledge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)

    op.create_unique_constraint(
        "uq_conversation_summaries_conversation_turns_covered",
        "conversation_summaries",
        ["conversation_id", "turns_covered_to"],
    )

    op.create_table(
        "quiz_attempt_summaries",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("concept_id", uuid_type, nullable=False),
        sa.Column("quiz_attempt_id", uuid_type, nullable=False),
        sa.Column("quiz_type", sa.String(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("strengths_json", sa.JSON(), nullable=False),
        sa.Column("gaps_json", sa.JSON(), nullable=False),
        sa.Column("question_fingerprints_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quiz_type in ('level_up', 'practice')",
            name="ck_quiz_attempt_summaries_quiz_type",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["concept_id"], ["concept_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["quiz_attempt_id"], ["quiz_attempts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quiz_attempt_id", name="uq_quiz_attempt_summaries_attempt"),
    )

    op.create_table(
        "learner_states",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("concept_id", uuid_type, nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("strengths_json", sa.JSON(), nullable=False),
        sa.Column("misconceptions_json", sa.JSON(), nullable=False),
        sa.Column("next_repair_targets_json", sa.JSON(), nullable=False),
        sa.Column("last_quiz_attempt_id", uuid_type, nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["concept_id"], ["concept_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["last_quiz_attempt_id"], ["quiz_attempts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "concept_id", name="uq_learner_states_workspace_concept"
        ),
    )


def downgrade() -> None:
    op.drop_table("learner_states")
    op.drop_table("quiz_attempt_summaries")
    op.drop_constraint(
        "uq_conversation_summaries_conversation_turns_covered",
        "conversation_summaries",
        type_="unique",
    )
