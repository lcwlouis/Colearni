"""Knowledge base document schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class KBDocumentSummary(BaseModel):
    document_id: int = Field(gt=0)
    public_id: str = Field(min_length=1)
    title: str | None = None
    summary: str | None = None
    source_uri: str | None = None
    chunk_count: int = Field(ge=0)
    ingestion_status: Literal["pending", "ingested"]
    graph_status: Literal["disabled", "pending", "extracting", "extracted", "failed"]
    graph_concept_count: int = Field(ge=0)
    created_at: datetime
    error_message: str | None = None


class KBDocumentListResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    documents: list[KBDocumentSummary]
