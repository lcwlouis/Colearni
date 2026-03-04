"""Initial PostgreSQL schema for Colearni.

Revision ID: 20260224_0001
Revises:
Create Date: 2026-02-24 00:00:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260224_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create the initial schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "workspaces",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name="fk_workspaces_owner_user_id_users"),
    )

    op.create_table(
        "workspace_members",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default=sa.text("'member'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_workspace_members_workspace_id_workspaces"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_workspace_members_user_id_users"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_workspace_user"),
        sa.CheckConstraint("role IN ('owner', 'member')", name="ck_workspace_members_role"),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_documents_workspace_id_workspaces"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], name="fk_documents_uploaded_by_user_id_users"),
        sa.UniqueConstraint("workspace_id", "content_hash", name="uq_documents_workspace_content_hash"),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("tsv", postgresql.TSVECTOR(), nullable=False, server_default=sa.text("''::tsvector")),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_chunks_workspace_id_workspaces"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_chunks_document_id_documents"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_chunk_index"),
    )

    op.create_table(
        "concepts_raw",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("chunk_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("context_snippet", sa.Text(), nullable=True),
        sa.Column("extracted_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_concepts_raw_workspace_id_workspaces"),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], name="fk_concepts_raw_chunk_id_chunks"),
    )

    op.create_table(
        "edges_raw",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("chunk_id", sa.BigInteger(), nullable=False),
        sa.Column("src_name", sa.Text(), nullable=False),
        sa.Column("tgt_name", sa.Text(), nullable=False),
        sa.Column("relation_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("weight", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_edges_raw_workspace_id_workspaces"),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], name="fk_edges_raw_chunk_id_chunks"),
        sa.CheckConstraint("weight >= 0", name="ck_edges_raw_weight_non_negative"),
    )

    op.create_table(
        "concepts_canon",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("aliases", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("dirty", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_concepts_canon_workspace_id_workspaces"),
        sa.UniqueConstraint("workspace_id", "canonical_name", name="uq_concepts_canon_workspace_canonical_name"),
    )

    op.create_table(
        "edges_canon",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("src_id", sa.BigInteger(), nullable=False),
        sa.Column("tgt_id", sa.BigInteger(), nullable=False),
        sa.Column("relation_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")),
        sa.Column("weight", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_edges_canon_workspace_id_workspaces"),
        sa.ForeignKeyConstraint(["src_id"], ["concepts_canon.id"], name="fk_edges_canon_src_id_concepts_canon"),
        sa.ForeignKeyConstraint(["tgt_id"], ["concepts_canon.id"], name="fk_edges_canon_tgt_id_concepts_canon"),
        sa.UniqueConstraint("workspace_id", "src_id", "tgt_id", "relation_type", name="uq_edges_canon_dedup"),
        sa.CheckConstraint("src_id <> tgt_id", name="ck_edges_canon_src_not_tgt"),
        sa.CheckConstraint("weight >= 0", name="ck_edges_canon_weight_non_negative"),
    )

    op.create_table(
        "provenance",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=False),
        sa.Column("chunk_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_provenance_workspace_id_workspaces"),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], name="fk_provenance_chunk_id_chunks"),
        sa.UniqueConstraint("workspace_id", "target_type", "target_id", "chunk_id", name="uq_provenance_target_chunk"),
        sa.CheckConstraint("target_type IN ('concept', 'edge')", name="ck_provenance_target_type"),
    )

    op.create_table(
        "concept_merge_map",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("alias", sa.Text(), nullable=False),
        sa.Column("canon_concept_id", sa.BigInteger(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("method", sa.Text(), nullable=False, server_default=sa.text("'exact'")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_concept_merge_map_workspace_id_workspaces"),
        sa.ForeignKeyConstraint(["canon_concept_id"], ["concepts_canon.id"], name="fk_concept_merge_map_canon_concept_id_concepts_canon"),
        sa.UniqueConstraint("workspace_id", "alias", name="uq_concept_merge_map_workspace_alias"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_concept_merge_map_confidence"),
        sa.CheckConstraint("method IN ('exact', 'lexical', 'vector', 'llm', 'manual')", name="ck_concept_merge_map_method"),
    )

    op.create_table(
        "concept_merge_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("from_id", sa.BigInteger(), nullable=False),
        sa.Column("to_id", sa.BigInteger(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_concept_merge_log_workspace_id_workspaces"),
        sa.ForeignKeyConstraint(["from_id"], ["concepts_canon.id"], name="fk_concept_merge_log_from_id_concepts_canon"),
        sa.ForeignKeyConstraint(["to_id"], ["concepts_canon.id"], name="fk_concept_merge_log_to_id_concepts_canon"),
        sa.CheckConstraint("from_id <> to_id", name="ck_concept_merge_log_from_not_to"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_concept_merge_log_confidence"),
        sa.CheckConstraint("method IN ('exact', 'lexical', 'vector', 'llm', 'manual')", name="ck_concept_merge_log_method"),
    )

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_chat_sessions_workspace_id_workspaces"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_chat_sessions_user_id_users"),
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], name="fk_chat_messages_session_id_chat_sessions"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_chat_messages_workspace_id_workspaces"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_chat_messages_user_id_users"),
        sa.CheckConstraint("type IN ('user', 'assistant', 'system', 'tool', 'card')", name="ck_chat_messages_type"),
    )

    op.create_table(
        "quizzes",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=True),
        sa.Column("concept_id", sa.BigInteger(), nullable=True),
        sa.Column("quiz_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_quizzes_workspace_id_workspaces"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_quizzes_user_id_users"),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], name="fk_quizzes_session_id_chat_sessions"),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts_canon.id"], name="fk_quizzes_concept_id_concepts_canon"),
        sa.CheckConstraint("quiz_type IN ('level_up', 'practice')", name="ck_quizzes_quiz_type"),
        sa.CheckConstraint("status IN ('draft', 'ready', 'submitted', 'graded')", name="ck_quizzes_status"),
    )

    op.create_table(
        "quiz_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("quiz_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], name="fk_quiz_items_quiz_id_quizzes"),
        sa.UniqueConstraint("quiz_id", "position", name="uq_quiz_items_quiz_position"),
        sa.CheckConstraint("position > 0", name="ck_quiz_items_position_positive"),
    )

    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("quiz_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("answers", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("grading", postgresql.JSONB(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("graded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], name="fk_quiz_attempts_quiz_id_quizzes"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_quiz_attempts_user_id_users"),
        sa.CheckConstraint("(score IS NULL) OR (score >= 0 AND score <= 1)", name="ck_quiz_attempts_score"),
    )

    op.create_table(
        "mastery",
        sa.Column("workspace_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("concept_id", sa.BigInteger(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'locked'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], name="fk_mastery_workspace_id_workspaces"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_mastery_user_id_users"),
        sa.ForeignKeyConstraint(["concept_id"], ["concepts_canon.id"], name="fk_mastery_concept_id_concepts_canon"),
        sa.PrimaryKeyConstraint("user_id", "concept_id", name="pk_mastery"),
        sa.CheckConstraint("score >= 0 AND score <= 1", name="ck_mastery_score"),
        sa.CheckConstraint("status IN ('locked', 'learning', 'learned')", name="ck_mastery_status"),
    )

    op.create_index("ix_workspaces_owner_user_id", "workspaces", ["owner_user_id"], unique=False)
    op.create_index("ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"], unique=False)
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"], unique=False)
    op.create_index("ix_documents_workspace_id", "documents", ["workspace_id"], unique=False)
    op.create_index("ix_documents_uploaded_by_user_id", "documents", ["uploaded_by_user_id"], unique=False)
    op.create_index("ix_chunks_workspace_id", "chunks", ["workspace_id"], unique=False)
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"], unique=False)
    op.create_index("ix_chunks_tsv_gin", "chunks", ["tsv"], unique=False, postgresql_using="gin")
    op.create_index("ix_concepts_raw_workspace_id", "concepts_raw", ["workspace_id"], unique=False)
    op.create_index("ix_concepts_raw_chunk_id", "concepts_raw", ["chunk_id"], unique=False)
    op.create_index("ix_edges_raw_workspace_id", "edges_raw", ["workspace_id"], unique=False)
    op.create_index("ix_edges_raw_chunk_id", "edges_raw", ["chunk_id"], unique=False)
    op.create_index("ix_concepts_canon_workspace_id", "concepts_canon", ["workspace_id"], unique=False)
    op.create_index("ix_edges_canon_workspace_id", "edges_canon", ["workspace_id"], unique=False)
    op.create_index("ix_edges_canon_src_id", "edges_canon", ["src_id"], unique=False)
    op.create_index("ix_edges_canon_tgt_id", "edges_canon", ["tgt_id"], unique=False)
    op.create_index("ix_provenance_workspace_id", "provenance", ["workspace_id"], unique=False)
    op.create_index("ix_provenance_chunk_id", "provenance", ["chunk_id"], unique=False)
    op.create_index("ix_concept_merge_map_workspace_id", "concept_merge_map", ["workspace_id"], unique=False)
    op.create_index("ix_concept_merge_map_canon_concept_id", "concept_merge_map", ["canon_concept_id"], unique=False)
    op.create_index("ix_concept_merge_log_workspace_id", "concept_merge_log", ["workspace_id"], unique=False)
    op.create_index("ix_concept_merge_log_from_id", "concept_merge_log", ["from_id"], unique=False)
    op.create_index("ix_concept_merge_log_to_id", "concept_merge_log", ["to_id"], unique=False)
    op.create_index("ix_chat_sessions_workspace_id", "chat_sessions", ["workspace_id"], unique=False)
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"], unique=False)
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"], unique=False)
    op.create_index("ix_chat_messages_workspace_id", "chat_messages", ["workspace_id"], unique=False)
    op.create_index("ix_chat_messages_user_id", "chat_messages", ["user_id"], unique=False)
    op.create_index("ix_quizzes_workspace_id", "quizzes", ["workspace_id"], unique=False)
    op.create_index("ix_quizzes_user_id", "quizzes", ["user_id"], unique=False)
    op.create_index("ix_quizzes_session_id", "quizzes", ["session_id"], unique=False)
    op.create_index("ix_quizzes_concept_id", "quizzes", ["concept_id"], unique=False)
    op.create_index("ix_quiz_items_quiz_id", "quiz_items", ["quiz_id"], unique=False)
    op.create_index("ix_quiz_attempts_quiz_id", "quiz_attempts", ["quiz_id"], unique=False)
    op.create_index("ix_quiz_attempts_user_id", "quiz_attempts", ["user_id"], unique=False)
    op.create_index("ix_mastery_workspace_id", "mastery", ["workspace_id"], unique=False)
    op.create_index("ix_mastery_user_id", "mastery", ["user_id"], unique=False)
    op.create_index("ix_mastery_concept_id", "mastery", ["concept_id"], unique=False)

    op.execute(
        "CREATE INDEX ix_concepts_canon_canonical_name_trgm "
        "ON concepts_canon USING gin (canonical_name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_concept_merge_map_alias_trgm "
        "ON concept_merge_map USING gin (alias gin_trgm_ops)"
    )


def downgrade() -> None:
    """Drop the initial schema."""
    op.drop_table("mastery")
    op.drop_table("quiz_attempts")
    op.drop_table("quiz_items")
    op.drop_table("quizzes")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    op.drop_table("concept_merge_log")
    op.drop_table("concept_merge_map")
    op.drop_table("provenance")
    op.drop_table("edges_canon")
    op.drop_table("concepts_canon")
    op.drop_table("edges_raw")
    op.drop_table("concepts_raw")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("workspace_members")
    op.drop_table("workspaces")
    op.drop_table("users")
