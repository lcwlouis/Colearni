"""Unit tests for learner_digest background job (AR6.1)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.jobs.learner_digest import (
    DIGEST_TYPES,
    MAX_USERS_PER_RUN,
    generate_deep_review,
    generate_frontier_suggestions,
    generate_learner_summary,
    run_learner_digest,
    store_digest,
)
from domain.learner.profile import LearnerProfileSnapshot, TopicStateSnapshot


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _snapshot(
    topics: list[TopicStateSnapshot] | None = None,
    session_summary: str = "",
) -> LearnerProfileSnapshot:
    return LearnerProfileSnapshot(
        workspace_id=1,
        user_id=10,
        topic_states=topics or [],
        recent_session_summary=session_summary,
    )


def _topic(
    cid: int,
    name: str,
    mastery: str = "intermediate",
    score: float = 0.6,
    readiness: float = 0.5,
    quiz: bool = False,
) -> TopicStateSnapshot:
    return TopicStateSnapshot(
        concept_id=cid,
        canonical_name=name,
        mastery_status=mastery,  # type: ignore[arg-type]
        mastery_score=score,
        readiness_score=readiness,
        recommend_quiz=quiz,
    )


# ---------------------------------------------------------------------------
# generate_learner_summary
# ---------------------------------------------------------------------------


class TestGenerateLearnerSummary:
    def test_empty_snapshot(self) -> None:
        result = generate_learner_summary(_snapshot())
        assert result["total_topics"] == 0
        assert result["mastery_distribution"]["unseen"] == 0

    def test_mixed_topics(self) -> None:
        topics = [
            _topic(1, "A", mastery="expert", score=0.9),
            _topic(2, "B", mastery="novice", score=0.2),
            _topic(3, "C", mastery="intermediate", score=0.6),
            _topic(4, "D", mastery="unseen", score=0.0),
        ]
        result = generate_learner_summary(_snapshot(topics))
        assert result["total_topics"] == 4
        dist = result["mastery_distribution"]
        assert dist["expert"] == 1
        assert dist["novice"] == 1
        assert dist["intermediate"] == 1
        assert dist["unseen"] == 1

    def test_includes_workspace_and_user(self) -> None:
        result = generate_learner_summary(_snapshot())
        assert result["workspace_id"] == 1
        assert result["user_id"] == 10


# ---------------------------------------------------------------------------
# generate_frontier_suggestions
# ---------------------------------------------------------------------------


class TestGenerateFrontierSuggestions:
    def test_empty_snapshot_no_suggestions(self) -> None:
        result = generate_frontier_suggestions(_snapshot())
        assert result["suggestions"] == []
        assert result["suggestion_count"] == 0

    def test_review_queue_first(self) -> None:
        topics = [
            _topic(1, "ReviewMe", quiz=True),
            _topic(2, "Frontier", mastery="intermediate"),
        ]
        result = generate_frontier_suggestions(_snapshot(topics), max_suggestions=1)
        assert len(result["suggestions"]) == 1
        assert result["suggestions"][0]["reason"] == "review_quiz_recommended"

    def test_frontier_sorted_by_readiness(self) -> None:
        topics = [
            _topic(1, "Low", mastery="intermediate", readiness=0.3),
            _topic(2, "High", mastery="intermediate", readiness=0.9),
        ]
        result = generate_frontier_suggestions(_snapshot(topics), max_suggestions=2)
        names = [s["name"] for s in result["suggestions"]]
        assert names[0] == "High"

    def test_weak_topics_as_fallback(self) -> None:
        topics = [
            _topic(1, "WeakOnly", mastery="novice", score=0.1, readiness=0.2),
        ]
        result = generate_frontier_suggestions(_snapshot(topics))
        assert result["suggestions"][0]["reason"] == "weak_needs_practice"

    def test_max_suggestions_cap(self) -> None:
        topics = [_topic(i, f"T{i}", quiz=True) for i in range(10)]
        result = generate_frontier_suggestions(_snapshot(topics), max_suggestions=3)
        assert len(result["suggestions"]) == 3

    def test_no_duplicates(self) -> None:
        # A topic that is both in review_queue and frontier should appear once
        topics = [
            _topic(1, "Both", mastery="intermediate", quiz=True),
        ]
        result = generate_frontier_suggestions(_snapshot(topics), max_suggestions=5)
        ids = [s["concept_id"] for s in result["suggestions"]]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# generate_deep_review
# ---------------------------------------------------------------------------


class TestGenerateDeepReview:
    def test_empty_snapshot(self) -> None:
        result = generate_deep_review(_snapshot())
        assert result["what_you_know"] == []
        assert result["what_seems_shaky"] == []
        assert result["what_to_review_next"] == []
        assert result["session_context"] is None

    def test_strong_topics_in_what_you_know(self) -> None:
        topics = [_topic(1, "Mastered", mastery="expert", score=0.95, readiness=0.8)]
        result = generate_deep_review(_snapshot(topics))
        assert "Mastered" in result["what_you_know"]

    def test_shaky_intermediate_topics(self) -> None:
        topics = [_topic(1, "Shaky", mastery="intermediate", score=0.55, readiness=0.3)]
        result = generate_deep_review(_snapshot(topics))
        assert len(result["what_seems_shaky"]) == 1
        assert result["what_seems_shaky"][0]["name"] == "Shaky"

    def test_session_context_included(self) -> None:
        result = generate_deep_review(_snapshot(session_summary="worked on calc"))
        assert result["session_context"] == "worked on calc"

    def test_weak_topics_as_review_fallback(self) -> None:
        topics = [_topic(1, "Weak", mastery="novice", score=0.1)]
        result = generate_deep_review(_snapshot(topics))
        assert "Weak" in result["what_to_review_next"]


# ---------------------------------------------------------------------------
# store_digest
# ---------------------------------------------------------------------------


class TestStoreDigest:
    def test_executes_insert(self) -> None:
        mock_session = MagicMock()
        store_digest(
            mock_session,
            workspace_id=1,
            user_id=10,
            digest_type="learner_summary",
            payload={"total_topics": 5},
        )
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["workspace_id"] == 1
        assert params["digest_type"] == "learner_summary"
        parsed = json.loads(params["payload"])
        assert parsed["total_topics"] == 5


# ---------------------------------------------------------------------------
# run_learner_digest (integration-style unit tests)
# ---------------------------------------------------------------------------


class _FakeMappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> "_FakeMappings":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class _FakeSession:
    def __init__(self, pairs: list[dict[str, Any]]) -> None:
        self.pairs = pairs
        self.executions: list[Any] = []
        self._first_call = True
        self.committed = False

    def execute(self, stmt: Any, params: Any = None) -> _FakeMappings:
        self.executions.append((stmt, params))
        if self._first_call:
            self._first_call = False
            return _FakeMappings(self.pairs)
        return _FakeMappings([])

    def commit(self) -> None:
        self.committed = True

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class TestRunLearnerDigest:
    def test_no_pairs_does_nothing(self, caplog: Any) -> None:
        mock_session = _FakeSession(pairs=[])
        with (
            patch("apps.jobs.learner_digest.create_db_engine"),
            patch("apps.jobs.learner_digest.Session", return_value=mock_session),
        ):
            import logging
            with caplog.at_level(logging.INFO):
                run_learner_digest()
        assert "Total digests stored: 0" in caplog.text

    def test_generates_three_digests_per_pair(self) -> None:
        pairs = [{"workspace_id": 1, "user_id": 10}]
        mock_session = _FakeSession(pairs=pairs)
        mock_snapshot = _snapshot()

        with (
            patch("apps.jobs.learner_digest.create_db_engine"),
            patch("apps.jobs.learner_digest.Session", return_value=mock_session),
            patch("apps.jobs.learner_digest.assemble_learner_snapshot", return_value=mock_snapshot),
        ):
            run_learner_digest()

        # 1 query for pairs + 3 INSERT statements for digests
        assert len(mock_session.executions) == 4
        assert mock_session.committed

    def test_continues_after_failure(self, caplog: Any) -> None:
        pairs = [
            {"workspace_id": 1, "user_id": 10},
            {"workspace_id": 1, "user_id": 20},
        ]
        mock_session = _FakeSession(pairs=pairs)
        call_count = 0

        def _assemble_side_effect(*args: Any, **kwargs: Any) -> LearnerProfileSnapshot:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("DB timeout")
            return _snapshot()

        with (
            patch("apps.jobs.learner_digest.create_db_engine"),
            patch("apps.jobs.learner_digest.Session", return_value=mock_session),
            patch("apps.jobs.learner_digest.assemble_learner_snapshot", side_effect=_assemble_side_effect),
        ):
            import logging
            with caplog.at_level(logging.INFO):
                run_learner_digest()

        assert "failed for workspace=1 user=10" in caplog.text
        assert "Total digests stored: 3" in caplog.text


class TestConstants:
    def test_max_users_bounded(self) -> None:
        assert MAX_USERS_PER_RUN <= 100

    def test_digest_types_defined(self) -> None:
        assert "learner_summary" in DIGEST_TYPES
        assert "frontier_suggestions" in DIGEST_TYPES
        assert "deep_review" in DIGEST_TYPES
