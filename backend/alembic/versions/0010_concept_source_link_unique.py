"""add concept source link uniqueness

Revision ID: 0010_link_unique
Revises: 0009_source_revisions
Create Date: 2026-05-25 00:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_link_unique"
down_revision: str | None = "0009_source_revisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_concept_source_links_source_concept_relation",
        "concept_source_links",
        ["source_id", "concept_id", "relation"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_concept_source_links_source_concept_relation",
        "concept_source_links",
        type_="unique",
    )
