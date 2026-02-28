"""Core Pydantic schemas — compatibility facade.

All schema definitions now live in feature-scoped sub-modules under
``core/schemas/``.  This ``__init__`` re-exports every public name so
that existing ``from core.schemas import X`` statements continue to
work without modification.

The sub-modules are:
  assistant, chat, graph, knowledge_base, practice, quizzes, research, workspaces
"""

from __future__ import annotations

# ── Re-exports from sub-modules ──────────────────────────────────────

from core.schemas.assistant import (  # noqa: F401
    ActionCTA,
    AssessmentCard,
    AssistantDraft,
    AssistantResponseEnvelope,
    AssistantResponseKind,
    CITATION_LABEL_FROM_NOTES,
    CITATION_LABEL_GENERAL_CONTEXT,
    Citation,
    CitationLabel,
    ConceptSwitchSuggestion,
    ConversationMeta,
    EvidenceItem,
    EvidenceSourceType,
    GroundingMode,
    ReadinessSnapshotResponse,
    ReadinessTopicState,
    RefusalReason,
    ResponseMode,
)
from core.schemas.chat import (  # noqa: F401
    ChatMessageRecord,
    ChatMessageType,
    ChatMessagesResponse,
    ChatRespondRequest,
    ChatSessionListResponse,
    ChatSessionSummary,
    ConceptSwitchDecision,
    OnboardingStatusResponse,
    OnboardingSuggestedTopic,
)
from core.schemas.graph import (  # noqa: F401
    GraphConceptDetail,
    GraphConceptDetailResponse,
    GraphConceptListResponse,
    GraphConceptSummary,
    GraphLuckyAdjacentScoreComponents,
    GraphLuckyPickAdjacent,
    GraphLuckyPickWildcard,
    GraphLuckyResponse,
    GraphLuckyWildcardScoreComponents,
    GraphSubgraphEdge,
    GraphSubgraphNode,
    GraphSubgraphResponse,
    LuckyMode,
)
from core.schemas.knowledge_base import (  # noqa: F401
    KBDocumentListResponse,
    KBDocumentSummary,
)
from core.schemas.practice import (  # noqa: F401
    FlashcardRateRequest,
    FlashcardRateResponse,
    FlashcardSelfRating,
    PracticeFlashcard,
    PracticeFlashcardsResponse,
    StatefulFlashcard,
    StatefulFlashcardsResponse,
)
from core.schemas.quizzes import (  # noqa: F401
    LevelUpQuizSubmitResponse,
    MasteryStatus,
    PracticeQuizSubmitResponse,
    QuizChoiceSummary,
    QuizCreateResponse,
    QuizFeedbackItem,
    QuizItemResult,
    QuizItemSummary,
    QuizItemType,
)
from core.schemas.research import (  # noqa: F401
    ResearchCandidateReviewRequest,
    ResearchCandidateSummary,
    ResearchRunSummary,
    ResearchSourceCreate,
    ResearchSourceSummary,
)

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
