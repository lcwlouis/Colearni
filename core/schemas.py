"""Core Pydantic schemas for grounded assistant responses."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class GroundingMode(str, Enum):
    """Grounding policy mode for assistant responses."""

    HYBRID = "hybrid"
    STRICT = "strict"


class EvidenceSourceType(str, Enum):
    """Origin type for evidence entries."""

    WORKSPACE = "workspace"
    GENERAL = "general"


class AssistantResponseKind(str, Enum):
    """Response variant emitted by the assistant."""

    ANSWER = "answer"
    REFUSAL = "refusal"


CITATION_LABEL_FROM_NOTES = "From your notes"
CITATION_LABEL_GENERAL_CONTEXT = "General context"

CitationLabel = Literal[CITATION_LABEL_FROM_NOTES, CITATION_LABEL_GENERAL_CONTEXT]
RefusalReason = Literal["insufficient_evidence", "invalid_citations"]


def _require_non_empty(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _ensure_unique_ids(values: list[str], *, field_name: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
            continue
        seen.add(value)

    if duplicates:
        duplicate_list = ", ".join(sorted(duplicates))
        raise ValueError(f"{field_name} values must be unique; duplicates: {duplicate_list}")


class EvidenceItem(BaseModel):
    """Evidence snippet with provenance metadata."""

    evidence_id: str = Field(min_length=1)
    source_type: EvidenceSourceType
    content: str = Field(min_length=1)
    document_id: int | None = Field(default=None, gt=0)
    chunk_id: int | None = Field(default=None, gt=0)
    chunk_index: int | None = Field(default=None, ge=0)
    document_title: str | None = None
    source_uri: str | None = None
    score: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator("evidence_id", "content")
    @classmethod
    def _normalize_required_fields(cls, value: str, info) -> str:  # noqa: ANN001
        return _require_non_empty(value, info.field_name)

    @model_validator(mode="after")
    def _validate_source_metadata(self) -> EvidenceItem:
        workspace_fields = ("document_id", "chunk_id", "chunk_index")

        if self.source_type == EvidenceSourceType.WORKSPACE:
            missing = [field for field in workspace_fields if getattr(self, field) is None]
            if missing:
                raise ValueError(
                    "workspace evidence requires document_id, chunk_id, and chunk_index; "
                    f"missing: {', '.join(missing)}"
                )
            return self

        populated = [field for field in workspace_fields if getattr(self, field) is not None]
        if populated:
            raise ValueError(
                "general evidence must not include document_id, chunk_id, or chunk_index; "
                f"found: {', '.join(populated)}"
            )
        return self


class Citation(BaseModel):
    """Citation that points to one evidence item."""

    citation_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    label: CitationLabel
    quote: str | None = None

    @field_validator("citation_id", "evidence_id")
    @classmethod
    def _normalize_required_fields(cls, value: str, info) -> str:  # noqa: ANN001
        return _require_non_empty(value, info.field_name)

    @field_validator("quote")
    @classmethod
    def _normalize_optional_quote(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_non_empty(value, "quote")


class AssistantDraft(BaseModel):
    """Pre-verification assistant output payload."""

    text: str = Field(min_length=1)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def _normalize_text(cls, value: str) -> str:
        return _require_non_empty(value, "text")

    @model_validator(mode="after")
    def _validate_unique_ids(self) -> AssistantDraft:
        _ensure_unique_ids([item.evidence_id for item in self.evidence], field_name="evidence_id")
        _ensure_unique_ids([item.citation_id for item in self.citations], field_name="citation_id")
        return self


class AssistantResponseEnvelope(BaseModel):
    """Verified assistant response payload returned to clients."""

    kind: AssistantResponseKind
    text: str = Field(min_length=1)
    grounding_mode: GroundingMode
    evidence: list[EvidenceItem] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    refusal_reason: RefusalReason | None = None

    @field_validator("text")
    @classmethod
    def _normalize_text(cls, value: str) -> str:
        return _require_non_empty(value, "text")

    @model_validator(mode="after")
    def _validate_envelope(self) -> AssistantResponseEnvelope:
        _ensure_unique_ids([item.evidence_id for item in self.evidence], field_name="evidence_id")
        _ensure_unique_ids([item.citation_id for item in self.citations], field_name="citation_id")

        if self.kind == AssistantResponseKind.ANSWER:
            if not self.citations:
                raise ValueError("answer responses must include at least one citation")
            if self.refusal_reason is not None:
                raise ValueError("answer responses must not include refusal_reason")
            return self

        if self.refusal_reason is None:
            raise ValueError("refusal responses must include refusal_reason")
        return self


class ChatRespondRequest(BaseModel):
    """Input payload for /chat/respond."""

    workspace_id: int = Field(gt=0)
    query: str = Field(min_length=1)
    user_id: int | None = Field(default=None, gt=0)
    concept_id: int | None = Field(default=None, gt=0)
    top_k: int = Field(default=5, ge=1)
    grounding_mode: GroundingMode | None = None

    @field_validator("query")
    @classmethod
    def _normalize_query(cls, value: str) -> str:
        return _require_non_empty(value, "query")


__all__ = [
    "AssistantDraft",
    "AssistantResponseEnvelope",
    "AssistantResponseKind",
    "CITATION_LABEL_FROM_NOTES",
    "CITATION_LABEL_GENERAL_CONTEXT",
    "ChatRespondRequest",
    "Citation",
    "CitationLabel",
    "EvidenceItem",
    "EvidenceSourceType",
    "GroundingMode",
    "RefusalReason",
]
