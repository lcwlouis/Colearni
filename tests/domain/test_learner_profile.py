"""Tests for learner profile snapshot types (AR4.1)."""

from __future__ import annotations

from domain.learner.profile import LearnerProfileSnapshot, TopicStateSnapshot


class TestTopicStateSnapshot:
    """Verify TopicStateSnapshot shape and helpers."""

    def test_default_unseen(self):
        t = TopicStateSnapshot(concept_id=1, canonical_name="Physics")
        assert t.mastery_status == "unseen"
        assert t.mastery_score is None
        assert t.readiness_score is None
        assert t.recommend_quiz is False
        assert t.recent_misconceptions == []
        assert t.last_interaction_days is None

    def test_is_weak_unseen(self):
        t = TopicStateSnapshot(concept_id=1, canonical_name="Physics")
        assert t.is_weak

    def test_is_weak_novice(self):
        t = TopicStateSnapshot(concept_id=1, canonical_name="Physics", mastery_status="novice")
        assert t.is_weak

    def test_is_weak_low_readiness(self):
        t = TopicStateSnapshot(
            concept_id=1, canonical_name="Physics",
            mastery_status="intermediate", readiness_score=0.2,
        )
        assert t.is_weak

    def test_not_weak_intermediate(self):
        t = TopicStateSnapshot(
            concept_id=1, canonical_name="Physics",
            mastery_status="intermediate", readiness_score=0.6,
        )
        assert not t.is_weak

    def test_is_strong_expert(self):
        t = TopicStateSnapshot(
            concept_id=1, canonical_name="Physics",
            mastery_status="expert", readiness_score=0.8,
        )
        assert t.is_strong

    def test_not_strong_low_readiness(self):
        t = TopicStateSnapshot(
            concept_id=1, canonical_name="Physics",
            mastery_status="expert", readiness_score=0.3,
        )
        assert not t.is_strong

    def test_frozen(self):
        t = TopicStateSnapshot(concept_id=1, canonical_name="Physics")
        try:
            t.mastery_status = "expert"  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestLearnerProfileSnapshot:
    """Verify LearnerProfileSnapshot shape and helpers."""

    def _make_profile(self) -> LearnerProfileSnapshot:
        return LearnerProfileSnapshot(
            workspace_id=1,
            user_id=1,
            topic_states=[
                TopicStateSnapshot(concept_id=1, canonical_name="Physics", mastery_status="unseen"),
                TopicStateSnapshot(concept_id=2, canonical_name="Math", mastery_status="intermediate", readiness_score=0.6),
                TopicStateSnapshot(concept_id=3, canonical_name="Chemistry", mastery_status="expert", readiness_score=0.9),
                TopicStateSnapshot(concept_id=4, canonical_name="Biology", mastery_status="novice", recommend_quiz=True),
                TopicStateSnapshot(concept_id=5, canonical_name="History", mastery_status="intermediate", readiness_score=0.2),
            ],
            recent_session_summary="Discussed photosynthesis.",
        )

    def test_weak_topics(self):
        profile = self._make_profile()
        weak = profile.weak_topics
        names = {t.canonical_name for t in weak}
        assert "Physics" in names  # unseen
        assert "Biology" in names  # novice
        assert "History" in names  # intermediate but low readiness

    def test_strong_topics(self):
        profile = self._make_profile()
        strong = profile.strong_topics
        assert len(strong) == 1
        assert strong[0].canonical_name == "Chemistry"

    def test_current_frontier(self):
        profile = self._make_profile()
        frontier = profile.current_frontier
        names = {t.canonical_name for t in frontier}
        assert "Math" in names
        assert "History" in names

    def test_review_queue(self):
        profile = self._make_profile()
        review = profile.review_queue
        assert len(review) == 1
        assert review[0].canonical_name == "Biology"

    def test_topic_by_id(self):
        profile = self._make_profile()
        t = profile.topic_by_id(3)
        assert t is not None
        assert t.canonical_name == "Chemistry"
        assert profile.topic_by_id(999) is None

    def test_summary_text(self):
        profile = self._make_profile()
        text = profile.summary_text()
        assert "Weak topics:" in text
        assert "Strong topics:" in text
        assert "Currently learning:" in text
        assert "Ready for review:" in text

    def test_summary_text_empty(self):
        profile = LearnerProfileSnapshot(workspace_id=1, user_id=1)
        assert profile.summary_text() == "No learner data available."

    def test_frozen(self):
        profile = self._make_profile()
        try:
            profile.workspace_id = 2  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass
