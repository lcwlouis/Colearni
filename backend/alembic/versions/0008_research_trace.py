"""add trail research traces

Revision ID: 0008_research_trace
Revises: 0007_reasoning_parts
Create Date: 2026-05-23 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_research_trace"
down_revision: str | None = "0007_reasoning_parts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = postgresql.UUID(as_uuid=True)

    op.create_table(
        "trail_research_traces",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("workspace_id", uuid_type, nullable=False),
        sa.Column("trail_id", uuid_type, nullable=False),
        sa.Column("trace_json", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trail_id"], ["trails.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trail_id", name="uq_trail_research_traces_trail_id"),
    )


def downgrade() -> None:
    op.drop_table("trail_research_traces")
