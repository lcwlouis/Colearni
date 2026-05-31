"""add flashcards subsystem + widen pin item_type

Revision ID: 0017_flashcards
Revises: 0016_pins
Create Date: 2026-05-31 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_flashcards"
down_revision: str | None = "0016_pins"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)

    op.create_table(
        "flashcard_decks",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("trail_id", uuid_type, nullable=False),
        sa.Column("concept_id", uuid_type, nullable=False),
        sa.Column("title", sa.String(), nullable=False),
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
        sa.UniqueConstraint(
            "workspace_id",
            "concept_id",
            name="uq_flashcard_decks_workspace_concept",
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trail_id"], ["trails.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["concept_id"], ["concept_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "flashcards",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("deck_id", uuid_type, nullable=False),
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("front", sa.String(), nullable=False),
        sa.Column("back", sa.String(), nullable=False),
        sa.Column("hint", sa.String(), nullable=True),
        sa.Column("source_ref", sa.String(), nullable=True),
        sa.Column("card_type", sa.String(), nullable=False),
        sa.Column("box", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_reviewed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lapses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "card_type in ('basic', 'cloze', 'reverse')",
            name="ck_flashcards_card_type",
        ),
        sa.ForeignKeyConstraint(["deck_id"], ["flashcard_decks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Widen the pin item_type CHECK so flashcard decks are pinnable like
    # artifacts/quiz attempts (Phase 15b added the constraint).
    op.drop_constraint("ck_pins_item_type", "pins", type_="check")
    op.create_check_constraint(
        "ck_pins_item_type",
        "pins",
        "item_type in ('artifact', 'quiz_attempt', 'flashcard')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_pins_item_type", "pins", type_="check")
    op.create_check_constraint(
        "ck_pins_item_type",
        "pins",
        "item_type in ('artifact', 'quiz_attempt')",
    )
    op.drop_table("flashcards")
    op.drop_table("flashcard_decks")
