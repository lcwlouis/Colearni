"""Tests for quiz resubmission behavior."""
import pytest
from unittest.mock import MagicMock, patch

from domain.learning.quiz_flow import submit_quiz


class FakeRow:
    """Behaves like a SQLAlchemy Row mapping."""
    def __init__(self, data):
        self._data = data
    def __getitem__(self, key):
        return self._data[key]
    def __contains__(self, key):
        return key in self._data
    def get(self, key, default=None):
        return self._data.get(key, default)


@pytest.fixture
def mock_session():
    return MagicMock()


@pytest.fixture
def base_answers():
    return [{"item_id": 1, "answer": "test answer"}]


def _quiz_row(quiz_type="practice"):
    return FakeRow({
        "id": 1,
        "user_id": 42,
        "workspace_id": 1,
        "concept_id": 10,
        "quiz_type": quiz_type,
        "status": "graded",
    })


def _item_row():
    return FakeRow({
        "item_id": 1,
        "item_type": "mcq",
        "prompt": "What is 2+2?",
        "position": 1,
        "payload": {"choices": [
            {"id": "a", "text": "3"},
            {"id": "b", "text": "4"},
        ], "correct_choice_id": "b"},
    })


def _existing_attempt():
    return FakeRow({
        "id": 99,
        "score": 0.5,
        "passed": False,
        "grading": {
            "items": [{"item_id": 1, "score": 0.5, "is_correct": False, "feedback": "old", "critical_misconception": False}],
            "overall_feedback": "old feedback",
            "critical_misconception": False,
        },
    })


@patch("domain.learning.quiz_flow._load_quiz_for_grading")
@patch("domain.learning.quiz_flow._load_quiz_items")
@patch("domain.learning.quiz_flow._load_existing_graded_attempt")
@patch("domain.learning.quiz_flow._grade_mcq_items")
@patch("domain.learning.quiz_flow._insert_attempt")
@patch("domain.learning.quiz_flow._mark_quiz_graded")
def test_practice_resubmit_grades_new_answers(
    mock_mark, mock_insert, mock_grade_mcq, mock_load_existing, mock_load_items, mock_load_quiz,
    mock_session, base_answers,
):
    """Practice quiz resubmit should NOT replay — it should grade fresh."""
    mock_load_quiz.return_value = _quiz_row("practice")
    mock_load_items.return_value = [_item_row()]
    mock_load_existing.return_value = _existing_attempt()
    mock_grade_mcq.return_value = [
        {"item_id": 1, "score": 1.0, "is_correct": True, "feedback": "correct!", "critical_misconception": False}
    ]
    mock_insert.return_value = 100

    result = submit_quiz(
        mock_session,
        quiz_id=1,
        workspace_id=1,
        user_id=42,
        answers=[{"item_id": 1, "answer": "b"}],
        llm_client=None,
        quiz_type="practice",
        update_mastery=False,
    )

    assert result["replayed"] is False
    assert mock_grade_mcq.called
    assert mock_insert.called


@patch("domain.learning.quiz_flow._load_quiz_for_grading")
@patch("domain.learning.quiz_flow._load_quiz_items")
@patch("domain.learning.quiz_flow._load_existing_graded_attempt")
def test_levelup_resubmit_replays(
    mock_load_existing, mock_load_items, mock_load_quiz,
    mock_session, base_answers,
):
    """Level-up quiz resubmit should still replay old result."""
    mock_load_quiz.return_value = _quiz_row("level_up")
    mock_load_items.return_value = [_item_row()]
    mock_load_existing.return_value = _existing_attempt()

    result = submit_quiz(
        mock_session,
        quiz_id=1,
        workspace_id=1,
        user_id=42,
        answers=[{"item_id": 1, "answer": "b"}],
        llm_client=None,
        quiz_type="level_up",
        update_mastery=False,
    )

    assert result["replayed"] is True
