"""Add document ingestion/graph status columns.

Revision ID: 0007
Revises: 0006
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa

revision = "20260228_0007"
down_revision = "20260228_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE documents
            ADD COLUMN IF NOT EXISTS ingestion_status VARCHAR(20) NOT NULL DEFAULT 'pending',
            ADD COLUMN IF NOT EXISTS graph_status VARCHAR(20) NOT NULL DEFAULT 'pending',
            ADD COLUMN IF NOT EXISTS error_message TEXT,
            ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS graph_extracted_at TIMESTAMPTZ;
    """)
    # Back-fill existing rows: if they already have chunks, mark as ingested
    op.execute("""
        UPDATE documents d
        SET ingestion_status = 'ingested',
            ingested_at = d.updated_at
        WHERE EXISTS (
            SELECT 1 FROM chunks c
            WHERE c.document_id = d.id AND c.workspace_id = d.workspace_id
        );
    """)
    # Back-fill graph_status for rows that have provenance
    op.execute("""
        UPDATE documents d
        SET graph_status = 'extracted',
            graph_extracted_at = d.updated_at
        WHERE EXISTS (
            SELECT 1 FROM chunks c
            JOIN provenance p ON p.chunk_id = c.id AND p.workspace_id = c.workspace_id
            WHERE c.document_id = d.id AND c.workspace_id = d.workspace_id
                AND p.target_type = 'concept'
        );
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE documents
            DROP COLUMN IF EXISTS ingestion_status,
            DROP COLUMN IF EXISTS graph_status,
            DROP COLUMN IF EXISTS error_message,
            DROP COLUMN IF EXISTS ingested_at,
            DROP COLUMN IF EXISTS graph_extracted_at;
    """)
