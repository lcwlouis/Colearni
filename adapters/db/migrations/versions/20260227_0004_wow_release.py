"""WOW Release schema: auth, UUIDs, readiness, stateful flashcards, research.

Revision ID: 20260227_0004
Revises: 20260224_0003
Create Date: 2026-02-27 00:00:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260227_0004"
down_revision: str = "20260224_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Add auth, UUID public IDs, readiness, stateful practice, and research tables."""

    # ── Slice 1 & 3: public_id columns on existing tables ──────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    for table in (
        "users", "workspaces", "documents", "chat_sessions", "quizzes", "concepts_canon",
    ):
        op.add_column(
            table,
            sa.Column(
                "public_id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
        )
        op.create_index(f"ix_{table}_public_id", table, ["public_id"], unique=True)

    # ── Slice 1: Auth tables ───────────────────────────────────────────
    op.create_table(
        "auth_magic_links",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_auth_magic_links_email", "auth_magic_links", ["email"])
    op.create_index("ix_auth_magic_links_token_hash", "auth_magic_links", ["token_hash"])

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_auth_sessions_user_id_users"
        ),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_public_id", "auth_sessions", ["public_id"], unique=True)
    op.create_index("ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"])

    # ── Slice 2: Workspace description & settings columns ────────────
    op.add_column(
        "workspaces",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "settings",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )

    # ── Slice 9: Readiness tables ──────────────────────────────────────
    op.create_table(
        "user_tutor_profile",
        sa.Column("user_id", sa.BigInteger(), primary_key=True),
        sa.Column("readiness_summary", sa.Text(), nullable=True),
        sa.Column("learning_style_notes", sa.Text(), nullable=True),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_tutor_profile_user_id_users"
        ),
    )

    op.create_table(
        "user_topic_state",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("concept_id", sa.BigInteger(), nullable=False),
        sa.Column("readiness_score", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("recommend_quiz", sa.Boolean(), nullable=False, server_default=sa.False_()),
        sa.Column("last_assessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_user_topic_state_workspace_id",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_topic_state_user_id"
        ),
        sa.ForeignKeyConstraint(
            ["concept_id"], ["concepts_canon.id"],
            name="fk_user_topic_state_concept_id",
        ),
        sa.UniqueConstraint(
            "workspace_id", "user_id", "concept_id",
            name="uq_user_topic_state_workspace_user_concept",
        ),
    )
    op.create_index("ix_user_topic_state_workspace_user", "user_topic_state", ["workspace_id", "user_id"])

    op.create_table(
        "tutor_readiness_snapshots",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_tutor_readiness_snapshots_workspace_id",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_tutor_readiness_snapshots_user_id",
        ),
    )
    op.create_index(
        "ix_tutor_readiness_snapshots_workspace_user",
        "tutor_readiness_snapshots",
        ["workspace_id", "user_id"],
    )

    # ── Slice 10/11: Stateful flashcard + practice novelty tables ──────
    op.create_table(
        "practice_generation_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            unique=True,
        ),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("concept_id", sa.BigInteger(), nullable=False),
        sa.Column("generation_type", sa.Text(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("has_more", sa.Boolean(), nullable=False, server_default=sa.True_()),
        sa.Column("exhausted_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_practice_generation_runs_workspace_id",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_practice_generation_runs_user_id",
        ),
        sa.ForeignKeyConstraint(
            ["concept_id"], ["concepts_canon.id"],
            name="fk_practice_generation_runs_concept_id",
        ),
        sa.CheckConstraint(
            "generation_type IN ('flashcard', 'quiz')",
            name="ck_practice_generation_runs_type",
        ),
    )
    op.create_index(
        "ix_practice_generation_runs_workspace_user_concept",
        "practice_generation_runs",
        ["workspace_id", "user_id", "concept_id"],
    )

    op.create_table(
        "practice_flashcard_bank",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "flashcard_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            unique=True,
        ),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("concept_id", sa.BigInteger(), nullable=False),
        sa.Column("front", sa.Text(), nullable=False),
        sa.Column("back", sa.Text(), nullable=False),
        sa.Column("hint", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["practice_generation_runs.id"],
            name="fk_practice_flashcard_bank_run_id",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_practice_flashcard_bank_workspace_id",
        ),
        sa.ForeignKeyConstraint(
            ["concept_id"], ["concepts_canon.id"],
            name="fk_practice_flashcard_bank_concept_id",
        ),
    )
    op.create_index(
        "ix_practice_flashcard_bank_workspace_concept",
        "practice_flashcard_bank",
        ["workspace_id", "concept_id"],
    )

    op.create_table(
        "practice_flashcard_progress",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("flashcard_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "self_rating",
            sa.Text(),
            nullable=True,
        ),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.False_()),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["flashcard_id"], ["practice_flashcard_bank.id"],
            name="fk_practice_flashcard_progress_flashcard_id",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_practice_flashcard_progress_user_id",
        ),
        sa.UniqueConstraint(
            "flashcard_id", "user_id",
            name="uq_practice_flashcard_progress_flashcard_user",
        ),
        sa.CheckConstraint(
            "self_rating IS NULL OR self_rating IN ('again', 'hard', 'good', 'easy')",
            name="ck_practice_flashcard_progress_rating",
        ),
    )

    op.create_table(
        "practice_item_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("concept_id", sa.BigInteger(), nullable=False),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_practice_item_history_workspace_id",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_practice_item_history_user_id",
        ),
        sa.ForeignKeyConstraint(
            ["concept_id"], ["concepts_canon.id"],
            name="fk_practice_item_history_concept_id",
        ),
    )
    op.create_index(
        "ix_practice_item_history_workspace_user_concept",
        "practice_item_history",
        ["workspace_id", "user_id", "concept_id"],
    )

    # ── Slice 12: Research tables ──────────────────────────────────────
    op.create_table(
        "workspace_research_sources",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.True_()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_workspace_research_sources_workspace_id",
        ),
        sa.UniqueConstraint(
            "workspace_id", "url",
            name="uq_workspace_research_sources_workspace_url",
        ),
    )
    op.create_index(
        "ix_workspace_research_sources_workspace_id",
        "workspace_research_sources",
        ["workspace_id"],
    )

    op.create_table(
        "workspace_research_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("candidates_found", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_workspace_research_runs_workspace_id",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_workspace_research_runs_status",
        ),
    )
    op.create_index(
        "ix_workspace_research_runs_workspace_id",
        "workspace_research_runs",
        ["workspace_id"],
    )

    op.create_table(
        "workspace_research_candidates",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("reviewed_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("document_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"],
            name="fk_workspace_research_candidates_workspace_id",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["workspace_research_runs.id"],
            name="fk_workspace_research_candidates_run_id",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"], ["users.id"],
            name="fk_workspace_research_candidates_reviewed_by",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"],
            name="fk_workspace_research_candidates_document_id",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'ingested')",
            name="ck_workspace_research_candidates_status",
        ),
    )
    op.create_index(
        "ix_workspace_research_candidates_workspace_id",
        "workspace_research_candidates",
        ["workspace_id"],
    )
    op.create_index(
        "ix_workspace_research_candidates_run_id",
        "workspace_research_candidates",
        ["run_id"],
    )


def downgrade() -> None:
    """Drop WOW release schema additions."""
    op.drop_table("workspace_research_candidates")
    op.drop_table("workspace_research_runs")
    op.drop_table("workspace_research_sources")
    op.drop_table("practice_item_history")
    op.drop_table("practice_flashcard_progress")
    op.drop_table("practice_flashcard_bank")
    op.drop_table("practice_generation_runs")
    op.drop_table("tutor_readiness_snapshots")
    op.drop_table("user_topic_state")
    op.drop_table("user_tutor_profile")
    op.drop_table("auth_sessions")
    op.drop_table("auth_magic_links")

    op.drop_column("workspaces", "settings")
    op.drop_column("workspaces", "description")

    for table in (
        "concepts_canon", "quizzes", "chat_sessions", "documents", "workspaces", "users",
    ):
        op.drop_index(f"ix_{table}_public_id", table_name=table)
        op.drop_column(table, "public_id")
