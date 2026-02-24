"""Core application layer package."""

from core.ingestion import (
    IngestionRequest,
    IngestionResult,
    IngestionValidationError,
    UnsupportedTextDocumentError,
    ingest_text_document,
)

__all__ = [
    "IngestionRequest",
    "IngestionResult",
    "IngestionValidationError",
    "UnsupportedTextDocumentError",
    "ingest_text_document",
]
