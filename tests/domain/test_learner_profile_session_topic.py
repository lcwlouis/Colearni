"""Tests that the current session topic is prepended to the learner profile summary."""

from __future__ import annotations

from domain.learner.profile import LearnerProfileSnapshot, TopicStateSnapshot


def _make_summary() -> str:
    """Build a realistic learner_profile_summary string."""
    profile = LearnerProfileSnapshot(
        workspace_id=1,
        user_id=1,
        topic_states=[
            TopicStateSnapshot(
                concept_id=10,
                canonical_name="Disk-based Database",
                mastery_status="intermediate",
                readiness_score=0.6,
            ),
        ],
    )
    return profile.summary_text()


def _prepend_session_topic(
    learner_profile_summary: str,
    session_topic_name: str | None,
    resolved_name: str | None,
) -> str:
    """Mirror the prepend logic used in stream.py / respond.py."""
    if session_topic_name:
        return f"Current session topic: {session_topic_name}; {learner_profile_summary}"
    elif resolved_name:
        return f"Current session topic: {resolved_name}; {learner_profile_summary}"
    return learner_profile_summary


class TestSessionTopicPrepend:
    def test_session_topic_prepended(self):
        summary = _make_summary()
        result = _prepend_session_topic(summary, "Storage of Relations", None)
        assert result.startswith("Current session topic: Storage of Relations;")
        assert "Currently learning:" in result

    def test_resolved_name_fallback(self):
        summary = _make_summary()
        result = _prepend_session_topic(summary, None, "B-Tree Indexing")
        assert result.startswith("Current session topic: B-Tree Indexing;")

    def test_no_topic_unchanged(self):
        summary = _make_summary()
        result = _prepend_session_topic(summary, None, None)
        assert result == summary
        assert not result.startswith("Current session topic:")

    def test_session_topic_takes_precedence_over_resolved(self):
        summary = _make_summary()
        result = _prepend_session_topic(summary, "Storage of Relations", "B-Tree Indexing")
        assert "Storage of Relations" in result
        assert "B-Tree Indexing" not in result
