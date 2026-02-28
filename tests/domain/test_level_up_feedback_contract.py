from __future__ import annotations

from domain.learning.quiz_grading import compose_feedback_items as _compose_feedback_items


def test_compose_feedback_items_maps_mcq_and_short_answer_results() -> None:
    item_refs = [
        {"item_id": 1, "item_type": "mcq"},
        {"item_id": 2, "item_type": "short_answer"},
    ]
    graded_items = [
        {
            "item_id": 1,
            "score": 1.0,
            "critical_misconception": False,
            "feedback": "Correct choice.",
        },
        {
            "item_id": 2,
            "score": 0.4,
            "critical_misconception": False,
            "feedback": "Partially correct explanation.",
        },
    ]

    payload = _compose_feedback_items(item_refs=item_refs, graded_items=graded_items)

    assert payload == [
        {
            "item_id": 1,
            "item_type": "mcq",
            "result": "correct",
            "is_correct": True,
            "critical_misconception": False,
            "feedback": "Correct choice.",
            "score": 1.0,
        },
        {
            "item_id": 2,
            "item_type": "short_answer",
            "result": "partial",
            "is_correct": False,
            "critical_misconception": False,
            "feedback": "Partially correct explanation.",
            "score": 0.4,
        },
    ]


def test_compose_feedback_items_marks_short_answer_critical_incorrect() -> None:
    payload = _compose_feedback_items(
        item_refs=[{"item_id": 10, "item_type": "short_answer"}],
        graded_items=[
            {
                "item_id": 10,
                "score": 1.0,
                "critical_misconception": True,
                "feedback": "Critical misunderstanding.",
            }
        ],
    )

    assert payload[0]["result"] == "incorrect"
    assert payload[0]["is_correct"] is False


def test_compose_feedback_items_filters_unknown_or_invalid_rows() -> None:
    payload = _compose_feedback_items(
        item_refs=[{"item_id": 1, "item_type": "mcq"}],
        graded_items=[
            {
                "item_id": 999,
                "score": 1.0,
                "critical_misconception": False,
                "feedback": "Ignore.",
            },
            {
                "item_id": 1,
                "score": "not-a-number",
                "critical_misconception": False,
                "feedback": "",
            },
            {"item_id": 1, "score": 0.0, "critical_misconception": False, "feedback": "Nope."},
        ],
    )

    assert payload == [
        {
            "item_id": 1,
            "item_type": "mcq",
            "result": "incorrect",
            "is_correct": False,
            "critical_misconception": False,
            "feedback": "Nope.",
            "score": 0.0,
        }
    ]
