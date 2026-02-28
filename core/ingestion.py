"""Core ingestion orchestration – compatibility facade.

All logic now lives in ``domain.ingestion``. This module re-exports public
names so that existing ``from core.ingestion import …`` statements keep working.
"""

from __future__ import annotations

# Re-export exception classes from the domain service
from domain.ingestion.service import (  # noqa: F401
    IngestionEmbeddingUnavailableError,
    IngestionGraphProviderError,
    IngestionGraphUnavailableError,
    IngestionValidationError,
    IngestionRequest,
    IngestionResult,
    ingest_text_document,
    ingest_text_document_fast,
)

# Re-export the background task entry-point
from domain.ingestion.post_ingest import run_post_ingest_tasks  # noqa: F401

# Re-export for callers that catch the parser-level error via core.ingestion
from adapters.parsers.text import UnsupportedTextDocumentError  # noqa: F401

__all__ = [
    "IngestionRequest",
    "IngestionResult",
    "IngestionEmbeddingUnavailableError",
    "IngestionGraphProviderError",
    "IngestionGraphUnavailableError",
    "IngestionValidationError",
    "UnsupportedTextDocumentError",
    "ingest_text_document",
    "ingest_text_document_fast",
    "run_post_ingest_tasks",
]
