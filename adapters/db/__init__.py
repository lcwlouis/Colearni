"""Database adapter package."""

from adapters.db.chat import (
    ChatNotFoundError,
    append_chat_message,
    assert_chat_session,
    count_chat_messages,
    create_chat_session,
    delete_chat_session,
    latest_system_summary,
    list_chat_messages,
    list_chat_sessions,
    list_recent_chat_messages,
    set_chat_session_title_if_missing,
)
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
    "ChatNotFoundError",
    "DocumentRow",
    "append_chat_message",
    "assert_chat_session",
    "count_chat_messages",
    "create_chat_session",
    "delete_chat_session",
    "count_chunks_for_document",
    "create_db_engine",
    "get_db_session",
    "get_document_by_content_hash",
    "get_document_by_id",
    "get_session_factory",
    "insert_chunks_bulk",
    "insert_document",
    "latest_system_summary",
    "list_chat_messages",
    "list_chat_sessions",
    "list_recent_chat_messages",
    "list_chunks_for_document",
    "new_session",
    "search_chunks_full_text",
    "set_chat_session_title_if_missing",
]
