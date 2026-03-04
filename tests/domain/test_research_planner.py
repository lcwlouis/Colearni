"""Tests for research planning types (AR5.1)."""

from __future__ import annotations

from domain.research.planner import (
    CandidatePromotionDecision,
    ResearchQuery,
    ResearchQueryPlan,
    TopicProposal,
)


class TestTopicProposal:
    """Verify TopicProposal shape and helpers."""

    def test_minimal(self):
        p = TopicProposal(topic="Machine Learning")
        assert p.topic == "Machine Learning"
        assert p.subtopics == []
        assert p.source_classes == []
        assert p.rationale == ""
        assert p.priority == "medium"
        assert not p.has_subtopics

    def test_with_subtopics(self):
        p = TopicProposal(
            topic="ML",
            subtopics=["Supervised Learning", "Neural Networks"],
            source_classes=["paper", "tutorial"],
            rationale="Core ML concepts",
            priority="high",
        )
        assert p.has_subtopics
        assert len(p.subtopics) == 2
        assert p.priority == "high"

    def test_frozen(self):
        p = TopicProposal(topic="ML")
        try:
            p.topic = "AI"  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestResearchQuery:
    """Verify ResearchQuery shape."""

    def test_defaults(self):
        q = ResearchQuery(query_text="transformers attention mechanism")
        assert q.source_class == "other"
        assert q.max_results == 10

    def test_custom(self):
        q = ResearchQuery(query_text="attention", source_class="paper", max_results=5)
        assert q.source_class == "paper"
        assert q.max_results == 5


class TestResearchQueryPlan:
    """Verify ResearchQueryPlan shape and helpers."""

    def test_empty_plan(self):
        plan = ResearchQueryPlan(topic="ML")
        assert plan.query_count == 0
        assert plan.is_bounded
        assert plan.max_total_candidates == 25

    def test_bounded_plan(self):
        queries = [ResearchQuery(query_text=f"q{i}") for i in range(5)]
        plan = ResearchQueryPlan(topic="ML", queries=queries, max_total_candidates=20)
        assert plan.query_count == 5
        assert plan.is_bounded

    def test_unbounded_too_many_queries(self):
        queries = [ResearchQuery(query_text=f"q{i}") for i in range(15)]
        plan = ResearchQueryPlan(topic="ML", queries=queries)
        assert not plan.is_bounded

    def test_unbounded_too_many_candidates(self):
        plan = ResearchQueryPlan(topic="ML", max_total_candidates=100)
        assert not plan.is_bounded

    def test_frozen(self):
        plan = ResearchQueryPlan(topic="ML")
        try:
            plan.topic = "AI"  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestCandidatePromotionDecision:
    """Verify CandidatePromotionDecision shape and helpers."""

    def test_promote(self):
        d = CandidatePromotionDecision(candidate_id=1, action="promote")
        assert d.is_promoting
        assert d.reason == ""

    def test_defer(self):
        d = CandidatePromotionDecision(candidate_id=2, action="defer", reason="Need more review")
        assert not d.is_promoting
        assert d.reason == "Need more review"

    def test_reject(self):
        d = CandidatePromotionDecision(candidate_id=3, action="reject")
        assert not d.is_promoting

    def test_quiz_gate(self):
        d = CandidatePromotionDecision(
            candidate_id=4, action="quiz_gate", requires_review_quiz=True,
        )
        assert d.is_promoting
        assert d.requires_review_quiz

    def test_frozen(self):
        d = CandidatePromotionDecision(candidate_id=1, action="promote")
        try:
            d.action = "reject"  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass
