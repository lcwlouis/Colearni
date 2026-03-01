"""Assistant response schemas: envelope, draft, evidence, citations, grounding."""

from __future__ import annotations

from datetime import datetime
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

# ResponseMode indicates how the answer was produced.
ResponseMode = Literal["grounded", "social", "clarify", "onboarding"]


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


class ConceptSwitchSuggestion(BaseModel):
    from_concept_id: int = Field(gt=0)
    from_concept_name: str = Field(min_length=1)
    to_concept_id: int = Field(gt=0)
    to_concept_name: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ConversationMeta(BaseModel):
    session_id: int | None = Field(default=None, gt=0)
    resolved_concept_id: int | None = Field(default=None, gt=0)
    resolved_concept_name: str | None = None
    concept_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    requires_clarification: bool = False
    concept_switch_suggestion: ConceptSwitchSuggestion | None = None


class AnswerParts(BaseModel):
    """Structured decomposition of an assistant answer.

    Replaces frontend regex-based hint extraction with a backend-controlled
    contract.  ``hint`` is ``None`` when the model did not include a hint.
    """

    body: str
    hint: str | None = None


class AssistantResponseEnvelope(BaseModel):
    """Verified assistant response payload returned to clients."""

    kind: AssistantResponseKind
    text: str = Field(min_length=1)
    grounding_mode: GroundingMode
    evidence: list[EvidenceItem] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    refusal_reason: RefusalReason | None = None
    conversation_meta: ConversationMeta | None = None
    response_mode: str = Field(default="grounded")
    actions: list[dict[str, object]] = Field(default_factory=list)
    generation_trace: GenerationTrace | None = None
    answer_parts: AnswerParts | None = None

    @field_validator("text")
    @classmethod
    def _normalize_text(cls, value: str) -> str:
        return _require_non_empty(value, "text")

    @model_validator(mode="after")
    def _validate_envelope(self) -> AssistantResponseEnvelope:
        _ensure_unique_ids([item.evidence_id for item in self.evidence], field_name="evidence_id")
        _ensure_unique_ids([item.citation_id for item in self.citations], field_name="citation_id")

        if self.kind == AssistantResponseKind.ANSWER:
            # Social and onboarding responses are exempt from citation requirements.
            if not self.citations and self.response_mode not in ("social", "onboarding", "clarify"):
                raise ValueError("answer responses must include at least one citation")
            if self.refusal_reason is not None:
                raise ValueError("answer responses must not include refusal_reason")
            return self

        if self.refusal_reason is None:
            raise ValueError("refusal responses must include refusal_reason")
        return self


class AssessmentCard(BaseModel):
    """Structured quiz/practice summary persisted as a 'card' message."""

    card_type: Literal["quiz_result", "practice_result"]
    quiz_id: int | None = Field(default=None, gt=0)
    concept_id: int | None = Field(default=None, gt=0)
    concept_name: str | None = None
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    summary: str = Field(min_length=1)


class ActionCTA(BaseModel):
    """Call-to-action surfaced inside the chat response envelope."""

    action_type: Literal["quiz_cta", "review_cta", "research_cta", "quiz_offer", "quiz_start"]
    label: str = Field(min_length=1)
    concept_id: int | None = Field(default=None, gt=0)
    concept_name: str | None = None


class GenerationTrace(BaseModel):
    """Safe operational trace metadata for a single LLM generation turn.

    Only operational fields are included — no prompt text, no chain-of-thought,
    no retrieved evidence body copies.

    Explicit reasoning control (U4):
    - ``reasoning_requested``: the *app* asked for explicit reasoning params.
    - ``reasoning_supported``: the model is known to support reasoning params.
    - ``reasoning_used``: explicit reasoning params were actually sent to the provider.
    - ``reasoning_effort``: the effort level requested (``"low"``/``"medium"``/``"high"``),
      or ``None`` if reasoning was not explicitly requested.
    - ``reasoning_effort_source``: where the effort value came from
      (``"settings"`` for env config, ``"override"`` for per-call override, ``None``
      if not applicable).  Reserved: a future first-layer model may set ``"override"``.

    Provider-reported reasoning metadata:
    - ``reasoning_tokens``: token count consumed by provider-internal reasoning
      (if reported).  This may be non-zero even when ``reasoning_requested`` is
      ``False`` — it reflects the provider's behaviour, not the app's request.

    Turn planner trace (AR1.4):
    - ``plan_intent``: classified query intent (e.g. ``"teach"``, ``"clarify"``).
    - ``plan_strategy``: resolved teaching strategy (e.g. ``"socratic"``, ``"direct"``).
    - ``plan_needs_retrieval``: whether the planner decided retrieval was needed.
    - ``plan_concept_hint``: concept hint from query analysis, if any.
    - ``plan_should_offer_quiz``: whether the planner suggests offering a quiz.
    - ``plan_should_start_quiz``: whether the planner wants to auto-start a quiz.

    Evidence plan trace (AR2.1):
    - ``evidence_plan_stop_reason``: why evidence retrieval stopped.
    - ``evidence_plan_budget``: retrieval budget used for evidence planning.
    - ``evidence_plan_chunk_count``: number of chunks retrieved by the evidence planner.
    """

    provider: str | None = None
    model: str | None = None
    timing_ms: float | None = Field(default=None, ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    reasoning_requested: bool | None = None
    reasoning_supported: bool | None = None
    reasoning_used: bool | None = None
    reasoning_effort: str | None = None
    reasoning_effort_source: str | None = None
    plan_intent: str | None = None
    plan_strategy: str | None = None
    plan_needs_retrieval: bool | None = None
    plan_concept_hint: str | None = None
    plan_should_offer_quiz: bool | None = None
    plan_should_start_quiz: bool | None = None
    evidence_plan_stop_reason: str | None = None
    evidence_plan_budget: int | None = None
    evidence_plan_chunk_count: int | None = None


class ReadinessTopicState(BaseModel):
    """Per-topic readiness summary for the readiness dashboard."""

    concept_id: int = Field(gt=0)
    concept_name: str = Field(min_length=1)
    readiness_score: float = Field(ge=0.0, le=1.0)
    recommend_quiz: bool
    last_assessed_at: datetime | None = None


class ReadinessSnapshotResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    topics: list[ReadinessTopicState]
