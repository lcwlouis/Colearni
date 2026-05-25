import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .types import SourceAccess, SourceOrigin


class SourceRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    origin: SourceOrigin
    access: SourceAccess
    title: str
    url: str | None
    license: str | None
    include_on_public_export: bool
    metadata_json: dict
    relation: str | None = None


class SourceRevisionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    source_id: uuid.UUID
    revision_number: int
    content_type: str | None
    file_size_bytes: int
    parser_name: str
    parser_version: str
    status: str
    error_message: str | None
    metadata_json: dict
    created_at: datetime


class SourceUploadResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    origin: SourceOrigin
    access: SourceAccess
    title: str
    url: str | None
    license: str | None
    include_on_public_export: bool
    metadata_json: dict
    revision: SourceRevisionSummary


class ConceptSourceLinkCreate(BaseModel):
    concept_id: uuid.UUID
    relation: str


class ConceptSourceLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    concept_id: uuid.UUID
    relation: str


class ConceptSourceListItem(BaseModel):
    """Safe, UI-facing summary of a source linked to a concept."""

    model_config = ConfigDict(from_attributes=True)

    source_id: uuid.UUID
    title: str
    origin: SourceOrigin
    access: SourceAccess
    url: str | None
    relation: str
    ingestion_status: str | None


class ConceptSourceLinksResponse(BaseModel):
    links: list[ConceptSourceLinkRead]


class ConceptSourcesResponse(BaseModel):
    sources: list[ConceptSourceListItem]
