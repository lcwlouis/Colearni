"""Tests for turn plan construction – AR1.2."""

from __future__ import annotations

from domain.chat.query_analyzer import QueryAnalysis
from domain.chat.turn_plan import TurnPlan, build_turn_plan


class TestBuildTurnPlan:
    """Unit tests for build_turn_plan()."""

    def _analysis(self, **overrides: object) -> QueryAnalysis:
        defaults = {
            "intent": "learn",
            "requested_mode": "unknown",
            "needs_retrieval": True,
            "should_offer_level_up": False,
            "high_level_keywords": [],
            "low_level_keywords": [],
            "concept_hints": [],
        }
        defaults.update(overrides)
        return QueryAnalysis(**defaults)  # type: ignore[arg-type]

    def test_learn_intent_socratic(self) -> None:
        plan = build_turn_plan(query_analysis=self._analysis())
        assert plan.intent == "learn"
        assert plan.teaching_strategy == "socratic"
        assert plan.needs_retrieval is True

    def test_learn_intent_direct_when_learned(self) -> None:
        plan = build_turn_plan(
            query_analysis=self._analysis(),
            mastery_status="learned",
        )
        assert plan.teaching_strategy == "direct"

    def test_learn_intent_direct_when_requested(self) -> None:
        plan = build_turn_plan(
            query_analysis=self._analysis(requested_mode="direct"),
        )
        assert plan.teaching_strategy == "direct"

    def test_social_intent(self) -> None:
        plan = build_turn_plan(
            query_analysis=self._analysis(intent="social", needs_retrieval=False),
        )
        assert plan.teaching_strategy == "social"
        assert plan.needs_retrieval is False

    def test_clarify_intent(self) -> None:
        plan = build_turn_plan(
            query_analysis=self._analysis(intent="clarify", needs_retrieval=False),
        )
        assert plan.teaching_strategy == "clarify"

    def test_onboarding_no_documents(self) -> None:
        plan = build_turn_plan(
            query_analysis=self._analysis(),
            has_documents=False,
        )
        assert plan.teaching_strategy == "onboarding"
        assert plan.needs_retrieval is False

    def test_level_up_intent(self) -> None:
        plan = build_turn_plan(
            query_analysis=self._analysis(intent="level_up"),
            resolved_concept_id=42,
        )
        assert plan.should_start_quiz is True
        assert plan.quiz_kind == "level_up"
        assert plan.quiz_concept_id == 42

    def test_offer_quiz_from_analysis(self) -> None:
        plan = build_turn_plan(
            query_analysis=self._analysis(should_offer_level_up=True),
            resolved_concept_id=7,
        )
        assert plan.should_offer_quiz is True
        assert plan.quiz_kind == "level_up"
        assert plan.quiz_concept_id == 7

    def test_concept_hint_from_resolved_name(self) -> None:
        plan = build_turn_plan(
            query_analysis=self._analysis(),
            resolved_concept_name="Mitosis",
        )
        assert plan.resolved_concept_hint == "Mitosis"

    def test_concept_hint_from_analysis_fallback(self) -> None:
        plan = build_turn_plan(
            query_analysis=self._analysis(concept_hints=["DNA replication"]),
        )
        assert plan.resolved_concept_hint == "DNA replication"

    def test_status_steps_with_retrieval(self) -> None:
        plan = build_turn_plan(query_analysis=self._analysis())
        assert "searching" in plan.status_steps
        assert "responding" in plan.status_steps

    def test_status_steps_without_retrieval(self) -> None:
        plan = build_turn_plan(
            query_analysis=self._analysis(intent="social", needs_retrieval=False),
        )
        assert "searching" not in plan.status_steps
        assert "responding" in plan.status_steps

    def test_frozen_immutability(self) -> None:
        plan = build_turn_plan(query_analysis=self._analysis())
        try:
            plan.intent = "social"  # type: ignore[misc]
            assert False, "should have raised"
        except AttributeError:
            pass

    def test_no_quiz_by_default(self) -> None:
        plan = build_turn_plan(query_analysis=self._analysis())
        assert plan.should_offer_quiz is False
        assert plan.should_start_quiz is False
        assert plan.quiz_kind == "none"
        assert plan.quiz_concept_id is None
