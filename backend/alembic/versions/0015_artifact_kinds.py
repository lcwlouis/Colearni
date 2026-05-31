"""widen artifacts.artifact_type CHECK to all Phase 15 kinds

The 0014 migration shipped the CHECK with only the first two read-only
templates ('worked_example', 'comparison_card'). Phases 15d/15e added
'timeline', 'mini_graph', and 'simulation_slider', which the model already
allows; this migration brings the DB CHECK in line so those kinds can persist.

Revision ID: 0015_artifact_kinds
Revises: 0014_artifacts
Create Date: 2026-05-31 00:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0015_artifact_kinds"
down_revision: str | None = "0014_artifacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALL_KINDS = (
    "artifact_type in ('worked_example', 'comparison_card', 'timeline', "
    "'mini_graph', 'simulation_slider')"
)
_OLD_KINDS = "artifact_type in ('worked_example', 'comparison_card')"


def upgrade() -> None:
    # Only Postgres enforces/needs this swap. SQLite (tests) builds schema from
    # the model via create_all, which already carries the widened CHECK, and the
    # SQLite dialect cannot ALTER a named CHECK in place.
    if op.get_bind().dialect.name != "postgresql":
        return
    op.drop_constraint("ck_artifacts_artifact_type", "artifacts", type_="check")
    op.create_check_constraint("ck_artifacts_artifact_type", "artifacts", _ALL_KINDS)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.drop_constraint("ck_artifacts_artifact_type", "artifacts", type_="check")
    op.create_check_constraint("ck_artifacts_artifact_type", "artifacts", _OLD_KINDS)
