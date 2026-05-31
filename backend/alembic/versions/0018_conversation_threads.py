"""allow multiple conversation threads per concept

Revision ID: 0018_conversation_threads
Revises: 0017_flashcards
Create Date: 2026-05-31 00:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0018_conversation_threads"
down_revision: str | None = "0017_flashcards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_conversations_workspace_trail_concept",
        "conversations",
        type_="unique",
    )


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_conversations_workspace_trail_concept",
        "conversations",
        ["workspace_id", "trail_id", "concept_id"],
    )
