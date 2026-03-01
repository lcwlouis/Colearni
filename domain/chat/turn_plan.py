"""Typed turn plan for conductor-driven tutor orchestration.

AR1.2: The TurnPlan captures routing decisions before execution starts.
It is populated from query analysis, concept context, mastery state,
and request parameters.  The plan is proposal-only and runtime-owned.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from domain.chat.query_analyzer import QueryAnalysis, Intent, RequestedMode

log = logging.getLogger("domain.chat.turn_plan")

TeachingStrategy = Literal["socratic", "direct", "clarify", "social", "onboarding"]
QuizKind = Literal["level_up", "practice", "none"]


@dataclass(frozen=True)
class TurnPlan:
    """Immutable plan that drives a single tutor turn.

    Fields are intentionally narrow and inspectable.
    """

    intent: Intent = "clarify"
    requested_mode: RequestedMode = "unknown"
    needs_retrieval: bool = True
    resolved_concept_hint: str | None = None
    teaching_strategy: TeachingStrategy = "socratic"
    research_need: bool = False
    should_offer_quiz: bool = False
    should_start_quiz: bool = False
    quiz_kind: QuizKind = "none"
    quiz_concept_id: int | None = None
    status_steps: list[str] = field(default_factory=list)


def build_turn_plan(
    *,
    query_analysis: QueryAnalysis,
    mastery_status: str | None = None,
    resolved_concept_name: str | None = None,
    resolved_concept_id: int | None = None,
    has_documents: bool = True,
) -> TurnPlan:
    """Assemble a TurnPlan from available signals.

    This function is the single construction point so plan logic
    is testable without running the full tutor flow.
    """
    intent = query_analysis.intent
    requested_mode = query_analysis.requested_mode
    needs_retrieval = query_analysis.needs_retrieval

    # Teaching strategy derivation
    if not has_documents:
        teaching_strategy: TeachingStrategy = "onboarding"
        needs_retrieval = False
    elif intent == "social":
        teaching_strategy = "social"
        needs_retrieval = False
    elif intent == "clarify":
        teaching_strategy = "clarify"
    elif mastery_status == "learned":
        teaching_strategy = "direct"
    elif requested_mode == "direct":
        teaching_strategy = "direct"
    else:
        teaching_strategy = "socratic"

    # Quiz hints
    should_offer_quiz = query_analysis.should_offer_level_up
    should_start_quiz = intent == "level_up"
    quiz_kind: QuizKind = "none"
    quiz_concept_id: int | None = None
    if should_start_quiz or should_offer_quiz:
        quiz_kind = "level_up"
        quiz_concept_id = resolved_concept_id

    # Status steps for stream protocol (preview; AR3 will refine)
    steps: list[str] = []
    if needs_retrieval:
        steps.append("searching")
    steps.append("responding")

    concept_hint = resolved_concept_name
    if not concept_hint and query_analysis.concept_hints:
        concept_hint = query_analysis.concept_hints[0]

    plan = TurnPlan(
        intent=intent,
        requested_mode=requested_mode,
        needs_retrieval=needs_retrieval,
        resolved_concept_hint=concept_hint,
        teaching_strategy=teaching_strategy,
        research_need=False,
        should_offer_quiz=should_offer_quiz,
        should_start_quiz=should_start_quiz,
        quiz_kind=quiz_kind,
        quiz_concept_id=quiz_concept_id,
        status_steps=steps,
    )

    log.info(
        "turn_plan intent=%s strategy=%s retrieval=%s quiz_offer=%s quiz_start=%s",
        plan.intent,
        plan.teaching_strategy,
        plan.needs_retrieval,
        plan.should_offer_quiz,
        plan.should_start_quiz,
    )
    return plan


__all__ = ["TurnPlan", "build_turn_plan"]
