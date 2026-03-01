"""Add learner_digests table for background job outputs.

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-01
"""

from alembic import op

revision = "20260301_0008"
down_revision = "20260228_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS learner_digests (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            workspace_id BIGINT NOT NULL REFERENCES workspaces(id),
            user_id BIGINT NOT NULL REFERENCES users(id),
            digest_type VARCHAR(40) NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ix_learner_digests_ws_user_type
            ON learner_digests (workspace_id, user_id, digest_type);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS learner_digests;")
