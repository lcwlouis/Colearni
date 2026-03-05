"""Add concept_id FK column to chat_sessions.

Revision ID: 20260305_0010
Revises: 20260301_0009
Create Date: 2026-03-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260305_0010"
down_revision: str = "20260301_0009"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions",
        sa.Column("concept_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_chat_sessions_concept_id_concepts_canon",
        "chat_sessions",
        "concepts_canon",
        ["concept_id"],
        ["id"],
    )
    op.create_index(
        "ix_chat_sessions_concept_id",
        "chat_sessions",
        ["concept_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_concept_id", table_name="chat_sessions")
    op.drop_constraint(
        "fk_chat_sessions_concept_id_concepts_canon",
        "chat_sessions",
        type_="foreignkey",
    )
    op.drop_column("chat_sessions", "concept_id")
