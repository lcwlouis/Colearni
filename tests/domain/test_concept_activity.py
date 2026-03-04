"""Tests for concept-activity aggregate surface (AR7.1)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from domain.learning.concept_activity import (
    get_concept_activity,
    _compute_affordances,
)


class TestGetConceptActivity:
    """Verify concept-activity aggregation logic."""

    def _mock_session(self, practice_rows=None, level_up_rows=None, flashcard_rows=None):
        """Build a mock session that returns different rows per query."""
        session = MagicMock()
        calls = []

        # Each call to session.execute returns a different result set
        if practice_rows is None:
            practice_rows = []
        if level_up_rows is None:
            level_up_rows = []
        if flashcard_rows is None:
            flashcard_rows = []

        for rows in [practice_rows, level_up_rows, flashcard_rows]:
            mock_result = MagicMock()
            mock_result.mappings.return_value.all.return_value = rows
            calls.append(mock_result)

        session.execute.side_effect = calls
        return session

    def test_empty_activity(self):
        session = self._mock_session()

        result = get_concept_activity(
            session, workspace_id=1, user_id=1, concept_id=10,
        )

        assert result["concept_id"] == 10
        assert result["practice_quizzes"]["count"] == 0
        assert result["level_up_quizzes"]["count"] == 0
        assert result["flashcard_runs"]["count"] == 0
        assert result["affordances"]["can_generate_flashcards"] is True
        assert result["affordances"]["has_prior_flashcards"] is False

    def test_practice_quiz_aggregation(self):
        rows = [
            {"quiz_id": 1, "title": "Q1", "score": 0.8, "passed": True, "graded_at": "2026-01-01"},
            {"quiz_id": 2, "title": "Q2", "score": 0.6, "passed": False, "graded_at": "2026-01-02"},
        ]
        session = self._mock_session(practice_rows=rows)

        result = get_concept_activity(
            session, workspace_id=1, user_id=1, concept_id=10,
        )

        pq = result["practice_quizzes"]
        assert pq["count"] == 2
        assert pq["average_score"] == 0.7
        assert pq["quizzes"][0]["quiz_id"] == 1
        assert pq["quizzes"][0]["can_retry"] is True

    def test_level_up_quiz_aggregation(self):
        rows = [
            {"quiz_id": 10, "title": "LU1", "score": 0.9, "passed": True,
             "graded_at": "2026-01-01", "critical_misconception": None},
            {"quiz_id": 11, "title": "LU2", "score": 0.4, "passed": False,
             "graded_at": "2026-01-02", "critical_misconception": "Missed key idea"},
        ]
        session = self._mock_session(level_up_rows=rows)

        result = get_concept_activity(
            session, workspace_id=1, user_id=1, concept_id=10,
        )

        lu = result["level_up_quizzes"]
        assert lu["count"] == 2
        assert lu["passed_count"] == 1
        assert lu["quizzes"][0]["can_promote"] is True
        assert lu["quizzes"][1]["can_promote"] is False
        assert lu["quizzes"][1]["critical_misconception"] == "Missed key idea"

    def test_flashcard_run_aggregation(self):
        rows = [
            {"run_id": "abc-123", "item_count": 6, "has_more": True,
             "exhausted_reason": None, "created_at": "2026-01-01"},
            {"run_id": "def-456", "item_count": 4, "has_more": False,
             "exhausted_reason": "bank_exhausted", "created_at": "2026-01-02"},
        ]
        session = self._mock_session(flashcard_rows=rows)

        result = get_concept_activity(
            session, workspace_id=1, user_id=1, concept_id=10,
        )

        fc = result["flashcard_runs"]
        assert fc["count"] == 2
        assert fc["total_cards_generated"] == 10
        assert fc["runs"][0]["can_open"] is True
        assert fc["runs"][1]["exhausted"] is True


class TestComputeAffordances:
    """Verify affordance computation."""

    def test_no_prior_activity(self):
        aff = _compute_affordances(
            {"count": 0}, {"count": 0}, {"count": 0},
        )
        assert aff["has_prior_flashcards"] is False
        assert aff["has_prior_practice"] is False
        assert aff["has_prior_level_up"] is False
        assert aff["can_generate_flashcards"] is True

    def test_with_prior_activity(self):
        aff = _compute_affordances(
            {"count": 2}, {"count": 1}, {"count": 3},
        )
        assert aff["has_prior_flashcards"] is True
        assert aff["has_prior_practice"] is True
        assert aff["has_prior_level_up"] is True
