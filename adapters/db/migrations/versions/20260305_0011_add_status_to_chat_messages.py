"""Add status column to chat_messages.

Revision ID: 20260305_0011
Revises: 20260305_0010
Create Date: 2026-03-05
"""

from __future__ import annotations

from alembic import op

revision: str = "20260305_0011"
down_revision: str = "20260305_0010"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE chat_messages
        ADD COLUMN status TEXT NOT NULL DEFAULT 'complete'
        """
    )
    op.execute(
        """
        CREATE INDEX ix_chat_messages_session_id_status
        ON chat_messages (session_id, status)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chat_messages_session_id_status")
    op.execute("ALTER TABLE chat_messages DROP COLUMN status")
