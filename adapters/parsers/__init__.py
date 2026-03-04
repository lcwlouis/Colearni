"""Parser adapters for document ingestion."""

from adapters.parsers.chunker import chunk_text_deterministic
from adapters.parsers.text import (
    ParsedTextDocument,
    UnsupportedTextDocumentError,
    parse_text_payload,
)

__all__ = [
    "ParsedTextDocument",
    "UnsupportedTextDocumentError",
    "chunk_text_deterministic",
    "parse_text_payload",
]
