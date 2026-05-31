"""add concept to pin item type check constraint

Revision ID: 0021_concept_pins
Revises: 0020_conversation_custom_titles
Create Date: 2025-01-01 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0021_concept_pins"
down_revision: str | None = "0020_conversation_custom_titles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_pins_item_type", "pins", type_="check")
    op.create_check_constraint(
        "ck_pins_item_type",
        "pins",
        "item_type in ('artifact', 'quiz_attempt', 'flashcard', 'concept')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_pins_item_type", "pins", type_="check")
    op.create_check_constraint(
        "ck_pins_item_type",
        "pins",
        "item_type in ('artifact', 'quiz_attempt', 'flashcard')",
    )
