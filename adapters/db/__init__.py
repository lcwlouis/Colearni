"""Database adapter package."""

from adapters.db.chunks import (
    ChunkRow,
    count_chunks_for_document,
    insert_chunks_bulk,
    list_chunks_for_document,
    search_chunks_full_text,
)
from adapters.db.dependencies import get_db_session
from adapters.db.documents import (
    DocumentRow,
    get_document_by_content_hash,
    get_document_by_id,
    insert_document,
)
from adapters.db.engine import create_db_engine
from adapters.db.session import get_session_factory, new_session

__all__ = [
    "ChunkRow",
    "DocumentRow",
    "count_chunks_for_document",
    "create_db_engine",
    "get_db_session",
    "get_document_by_content_hash",
    "get_document_by_id",
    "get_session_factory",
    "insert_chunks_bulk",
    "insert_document",
    "list_chunks_for_document",
    "new_session",
    "search_chunks_full_text",
]
