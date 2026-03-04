"""Canonical learner profile and topic-state snapshot types (AR4.1).

These are *read-model* snapshots assembled from existing data sources
(mastery table, user_topic_state, session memory).  They do not own or
replace any of those sources — they merely present a coherent view for
tutor planning, research planning, and review policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


MasteryLevel = Literal["unseen", "novice", "intermediate", "expert"]


@dataclass(frozen=True, slots=True)
class TopicStateSnapshot:
    """Per-topic learner state for a single concept.

    All fields derive from existing DB truth (mastery table,
    user_topic_state, session context).  None/default means "no data".
    """

    concept_id: int
    canonical_name: str
    mastery_status: MasteryLevel = "unseen"
    mastery_score: float | None = None
    readiness_score: float | None = None
    recommend_quiz: bool = False
    recent_misconceptions: list[str] = field(default_factory=list)
    last_interaction_days: float | None = None

    @property
    def is_weak(self) -> bool:
        """True if mastery is below intermediate or readiness is low."""
        if self.mastery_status in ("unseen", "novice"):
            return True
        if self.readiness_score is not None and self.readiness_score < 0.4:
            return True
        return False

    @property
    def is_strong(self) -> bool:
        """True if mastery is expert and readiness is adequate."""
        return (
            self.mastery_status == "expert"
            and (self.readiness_score is None or self.readiness_score >= 0.6)
        )


@dataclass(frozen=True, slots=True)
class LearnerProfileSnapshot:
    """Aggregated learner profile for a workspace+user pair.

    Assembling this snapshot is the job of the assembly service (AR4.2).
    The snapshot is immutable and cheap to pass around.
    """

    workspace_id: int
    user_id: int
    topic_states: list[TopicStateSnapshot] = field(default_factory=list)
    recent_session_summary: str = ""

    @property
    def weak_topics(self) -> list[TopicStateSnapshot]:
        """Topics that need more work."""
        return [t for t in self.topic_states if t.is_weak]

    @property
    def strong_topics(self) -> list[TopicStateSnapshot]:
        """Topics the learner has mastered."""
        return [t for t in self.topic_states if t.is_strong]

    @property
    def review_queue(self) -> list[TopicStateSnapshot]:
        """Topics where a quiz is recommended."""
        return [t for t in self.topic_states if t.recommend_quiz]

    @property
    def current_frontier(self) -> list[TopicStateSnapshot]:
        """Topics at the learning edge (intermediate mastery, not yet expert)."""
        return [
            t for t in self.topic_states
            if t.mastery_status == "intermediate"
        ]

    def topic_by_id(self, concept_id: int) -> TopicStateSnapshot | None:
        """Look up a specific topic by concept_id."""
        for t in self.topic_states:
            if t.concept_id == concept_id:
                return t
        return None

    def summary_text(self, max_topics: int = 5) -> str:
        """Return a short text summary suitable for prompt injection."""
        parts: list[str] = []
        weak = self.weak_topics[:max_topics]
        if weak:
            names = ", ".join(t.canonical_name for t in weak)
            parts.append(f"Weak topics: {names}")
        strong = self.strong_topics[:max_topics]
        if strong:
            names = ", ".join(t.canonical_name for t in strong)
            parts.append(f"Strong topics: {names}")
        frontier = self.current_frontier[:max_topics]
        if frontier:
            names = ", ".join(t.canonical_name for t in frontier)
            parts.append(f"Currently learning: {names}")
        review = self.review_queue[:max_topics]
        if review:
            names = ", ".join(t.canonical_name for t in review)
            parts.append(f"Ready for review: {names}")
        return "; ".join(parts) if parts else "No learner data available."
