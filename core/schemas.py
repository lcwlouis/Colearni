"""Core Pydantic schemas for grounded assistant responses."""

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
ConceptSwitchDecision = Literal["accept", "reject"]


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
            if not self.citations and self.response_mode not in ("social", "onboarding"):
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
    session_id: int | None = Field(default=None, gt=0)
    user_id: int | None = Field(default=None, gt=0)
    concept_id: int | None = Field(default=None, gt=0)
    suggested_concept_id: int | None = Field(default=None, gt=0)
    concept_switch_decision: ConceptSwitchDecision | None = None
    top_k: int = Field(default=5, ge=1)
    grounding_mode: GroundingMode | None = None

    @field_validator("query")
    @classmethod
    def _normalize_query(cls, value: str) -> str:
        return _require_non_empty(value, "query")


ChatMessageType = Literal["user", "assistant", "system", "tool", "card"]


class ChatSessionSummary(BaseModel):
    session_id: int = Field(gt=0)
    public_id: str = Field(min_length=1)
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    title: str | None = None
    last_activity_at: datetime


class ChatSessionListResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    sessions: list[ChatSessionSummary]


class ChatMessageRecord(BaseModel):
    message_id: int = Field(gt=0)
    session_id: int = Field(gt=0)
    type: ChatMessageType
    payload: dict[str, object]
    created_at: datetime


class ChatMessagesResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    session_id: int = Field(gt=0)
    messages: list[ChatMessageRecord]


QuizItemType = Literal["short_answer", "mcq"]
QuizItemResult = Literal["correct", "partial", "incorrect"]
MasteryStatus = Literal["locked", "learning", "learned"]
LuckyMode = Literal["adjacent", "wildcard"]


class QuizItemSummary(BaseModel):
    item_id: int = Field(gt=0)
    position: int = Field(ge=1)
    item_type: QuizItemType
    prompt: str = Field(min_length=1)
    choices: list["QuizChoiceSummary"] | None


class QuizChoiceSummary(BaseModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class QuizCreateResponse(BaseModel):
    quiz_id: int = Field(gt=0)
    workspace_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    concept_id: int = Field(gt=0)
    status: str = Field(min_length=1)
    items: list[QuizItemSummary] = Field(min_length=1)


class QuizFeedbackItem(BaseModel):
    item_id: int = Field(gt=0)
    item_type: QuizItemType
    result: QuizItemResult
    is_correct: bool
    critical_misconception: bool
    feedback: str = Field(min_length=1)
    score: float | None = Field(default=None, ge=0.0, le=1.0)


class PracticeQuizSubmitResponse(BaseModel):
    quiz_id: int = Field(gt=0)
    attempt_id: int = Field(gt=0)
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    critical_misconception: bool
    overall_feedback: str = Field(min_length=1)
    items: list[QuizFeedbackItem] = Field(min_length=1)
    replayed: bool
    retry_hint: str | None


class LevelUpQuizSubmitResponse(PracticeQuizSubmitResponse):
    mastery_status: MasteryStatus
    mastery_score: float = Field(ge=0.0, le=1.0)


class PracticeFlashcard(BaseModel):
    front: str = Field(min_length=1)
    back: str = Field(min_length=1)
    hint: str = Field(min_length=1)


class PracticeFlashcardsResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    concept_id: int = Field(gt=0)
    concept_name: str = Field(min_length=1)
    flashcards: list[PracticeFlashcard] = Field(min_length=1)


class GraphConceptDetail(BaseModel):
    concept_id: int = Field(gt=0)
    canonical_name: str = Field(min_length=1)
    description: str
    aliases: list[str] = Field(default_factory=list)
    degree: int = Field(ge=0)


class GraphConceptDetailResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    concept: GraphConceptDetail


class GraphConceptSummary(BaseModel):
    concept_id: int = Field(gt=0)
    canonical_name: str = Field(min_length=1)
    description: str
    degree: int = Field(ge=0)
    mastery_status: MasteryStatus | None = None
    mastery_score: float | None = Field(default=None, ge=0.0, le=1.0)


class GraphConceptListResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    user_id: int | None = Field(default=None, gt=0)
    concepts: list[GraphConceptSummary]


class GraphSubgraphNode(BaseModel):
    concept_id: int = Field(gt=0)
    canonical_name: str = Field(min_length=1)
    description: str
    hop_distance: int = Field(ge=0)
    mastery_status: MasteryStatus | None = None
    mastery_score: float | None = Field(default=None, ge=0.0, le=1.0)


class GraphSubgraphEdge(BaseModel):
    edge_id: int = Field(gt=0)
    src_concept_id: int = Field(gt=0)
    tgt_concept_id: int = Field(gt=0)
    relation_type: str = Field(min_length=1)
    description: str
    keywords: list[str] = Field(default_factory=list)
    weight: float


class GraphSubgraphResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    root_concept_id: int | None = Field(default=None, gt=0)
    max_hops: int | None = Field(default=None, ge=1)
    nodes: list[GraphSubgraphNode]
    edges: list[GraphSubgraphEdge]
    is_truncated: bool = Field(default=False, description="True when results were capped by max_nodes/max_edges")
    total_concept_count: int | None = Field(default=None, ge=0, description="Total concepts in scope before truncation")


class GraphLuckyAdjacentScoreComponents(BaseModel):
    hop_distance: int = Field(ge=0)
    strongest_link_weight: float


class GraphLuckyWildcardScoreComponents(BaseModel):
    degree: int = Field(ge=0)
    total_incident_weight: float


class GraphLuckyPickAdjacent(BaseModel):
    concept_id: int = Field(gt=0)
    canonical_name: str = Field(min_length=1)
    description: str
    hop_distance: int = Field(ge=0)
    score_components: GraphLuckyAdjacentScoreComponents


class GraphLuckyPickWildcard(BaseModel):
    concept_id: int = Field(gt=0)
    canonical_name: str = Field(min_length=1)
    description: str
    hop_distance: None = None
    score_components: GraphLuckyWildcardScoreComponents


class GraphLuckyResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    seed_concept_id: int = Field(gt=0)
    mode: LuckyMode
    pick: GraphLuckyPickAdjacent | GraphLuckyPickWildcard

    @model_validator(mode="after")
    def _validate_pick_mode(self) -> GraphLuckyResponse:
        if self.mode == "adjacent" and isinstance(self.pick, GraphLuckyPickWildcard):
            raise ValueError("adjacent mode requires adjacent pick payload")
        if self.mode == "wildcard" and isinstance(self.pick, GraphLuckyPickAdjacent):
            raise ValueError("wildcard mode requires wildcard pick payload")
        return self


# ── Slice 3+4: UUID-based envelope IDs ────────────────────────────────

# ResponseMode indicates whether the answer came from grounded retrieval or
# social/chitchat handling (Slice 13).
ResponseMode = Literal["grounded", "social"]


# ── Slice 6: Knowledge-base explorer schemas ──────────────────────────


class KBDocumentSummary(BaseModel):
    document_id: int = Field(gt=0)
    public_id: str = Field(min_length=1)
    title: str | None = None
    summary: str | None = None
    source_uri: str | None = None
    chunk_count: int = Field(ge=0)
    ingestion_status: Literal["pending", "ingested"]
    graph_status: Literal["disabled", "pending", "extracted"]
    graph_concept_count: int = Field(ge=0)
    created_at: datetime


class KBDocumentListResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    documents: list[KBDocumentSummary]


# ── Slice 7: Assessment card persisted in chat ────────────────────────


class AssessmentCard(BaseModel):
    """Structured quiz/practice summary persisted as a 'card' message."""

    card_type: Literal["quiz_result", "practice_result"]
    quiz_id: int | None = Field(default=None, gt=0)
    concept_id: int | None = Field(default=None, gt=0)
    concept_name: str | None = None
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    summary: str = Field(min_length=1)


# ── Slice 9: Readiness CTA actions ───────────────────────────────────


class ActionCTA(BaseModel):
    """Call-to-action surfaced inside the chat response envelope."""

    action_type: Literal["quiz_cta", "review_cta", "research_cta"]
    label: str = Field(min_length=1)
    concept_id: int | None = Field(default=None, gt=0)
    concept_name: str | None = None


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


# ── Slice 10: Stateful flashcard responses ────────────────────────────

FlashcardSelfRating = Literal["again", "hard", "good", "easy"]


class StatefulFlashcard(BaseModel):
    flashcard_id: str = Field(min_length=1)
    front: str = Field(min_length=1)
    back: str = Field(min_length=1)
    hint: str = Field(min_length=1)
    self_rating: FlashcardSelfRating | None = None
    passed: bool = False


class StatefulFlashcardsResponse(BaseModel):
    workspace_id: int = Field(gt=0)
    concept_id: int = Field(gt=0)
    concept_name: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    flashcards: list[StatefulFlashcard]
    has_more: bool = True
    exhausted_reason: str | None = None


class FlashcardRateRequest(BaseModel):
    flashcard_id: str = Field(min_length=1)
    self_rating: FlashcardSelfRating


class FlashcardRateResponse(BaseModel):
    flashcard_id: str
    self_rating: FlashcardSelfRating
    passed: bool


# ── Slice 12: Research agent schemas ──────────────────────────────────


class ResearchSourceCreate(BaseModel):
    url: str = Field(min_length=1)
    label: str | None = None


class ResearchSourceSummary(BaseModel):
    source_id: int = Field(gt=0)
    url: str
    label: str | None = None
    active: bool


class ResearchRunSummary(BaseModel):
    run_id: int = Field(gt=0)
    status: Literal["pending", "running", "completed", "failed"]
    candidates_found: int = Field(ge=0)
    started_at: datetime
    finished_at: datetime | None = None


class ResearchCandidateSummary(BaseModel):
    candidate_id: int = Field(gt=0)
    source_url: str
    title: str | None = None
    snippet: str | None = None
    status: Literal["pending", "approved", "rejected", "ingested"]


class ResearchCandidateReviewRequest(BaseModel):
    status: Literal["approved", "rejected"]


# ── Onboarding ──────────────────────────────────


class OnboardingSuggestedTopic(BaseModel):
    concept_id: int = Field(gt=0)
    canonical_name: str
    description: str | None = None
    degree: int = Field(ge=0)


class OnboardingStatusResponse(BaseModel):
    has_documents: bool
    has_active_concepts: bool
    suggested_topics: list[OnboardingSuggestedTopic] = Field(default_factory=list)


__all__ = [
    "ActionCTA",
    "AssessmentCard",
    "AssistantDraft",
    "AssistantResponseEnvelope",
    "AssistantResponseKind",
    "CITATION_LABEL_FROM_NOTES",
    "CITATION_LABEL_GENERAL_CONTEXT",
    "ChatRespondRequest",
    "ChatMessageRecord",
    "ChatMessageType",
    "ChatMessagesResponse",
    "ChatSessionListResponse",
    "ChatSessionSummary",
    "Citation",
    "CitationLabel",
    "ConceptSwitchDecision",
    "ConceptSwitchSuggestion",
    "ConversationMeta",
    "EvidenceItem",
    "EvidenceSourceType",
    "FlashcardRateRequest",
    "FlashcardRateResponse",
    "FlashcardSelfRating",
    "GraphConceptDetail",
    "GraphConceptDetailResponse",
    "GraphConceptListResponse",
    "GraphConceptSummary",
    "GraphLuckyAdjacentScoreComponents",
    "GraphLuckyPickAdjacent",
    "GraphLuckyPickWildcard",
    "GraphLuckyResponse",
    "GraphLuckyWildcardScoreComponents",
    "GraphSubgraphEdge",
    "GraphSubgraphNode",
    "GraphSubgraphResponse",
    "GroundingMode",
    "KBDocumentListResponse",
    "KBDocumentSummary",
    "LevelUpQuizSubmitResponse",
    "LuckyMode",
    "MasteryStatus",
    "OnboardingStatusResponse",
    "OnboardingSuggestedTopic",
    "PracticeFlashcard",
    "PracticeFlashcardsResponse",
    "PracticeQuizSubmitResponse",
    "QuizChoiceSummary",
    "QuizCreateResponse",
    "QuizFeedbackItem",
    "QuizItemResult",
    "QuizItemSummary",
    "QuizItemType",
    "ReadinessSnapshotResponse",
    "ReadinessTopicState",
    "RefusalReason",
    "ResearchCandidateReviewRequest",
    "ResearchCandidateSummary",
    "ResearchRunSummary",
    "ResearchSourceCreate",
    "ResearchSourceSummary",
    "ResponseMode",
    "StatefulFlashcard",
    "StatefulFlashcardsResponse",
]
