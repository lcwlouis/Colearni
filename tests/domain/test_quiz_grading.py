"""Tests for quiz grading – Pydantic-based parse_grading validation."""

from __future__ import annotations

import json

import pytest

from domain.learning.quiz_grading import QuizGradingError, parse_grading


def _valid_payload(item_ids: list[int] | None = None) -> dict:
    ids = item_ids or [1, 2]
    return {
        "items": [
            {
                "item_id": iid,
                "score": 0.8,
                "critical_misconception": False,
                "feedback": f"Good answer for item {iid}.",
            }
            for iid in ids
        ],
        "overall_feedback": "Solid understanding overall.",
    }


class TestParseGradingValid:
    def test_valid_json_string(self) -> None:
        result = parse_grading(json.dumps(_valid_payload()), [1, 2])
        assert len(result["items"]) == 2
        assert result["overall_feedback"] == "Solid understanding overall."

    def test_valid_dict_input(self) -> None:
        result = parse_grading(_valid_payload(), [1, 2])
        assert result["items"][0]["score"] == 0.8

    def test_strips_code_fences(self) -> None:
        raw = "```json\n" + json.dumps(_valid_payload()) + "\n```"
        result = parse_grading(raw, [1, 2])
        assert len(result["items"]) == 2

    def test_preserves_item_order(self) -> None:
        result = parse_grading(json.dumps(_valid_payload([3, 1])), [1, 3])
        assert result["items"][0]["item_id"] == 1
        assert result["items"][1]["item_id"] == 3


class TestParseGradingErrors:
    def test_invalid_json_raises(self) -> None:
        with pytest.raises(QuizGradingError, match="not valid JSON"):
            parse_grading("not json", [1])

    def test_missing_items_raises(self) -> None:
        with pytest.raises(QuizGradingError, match="not valid JSON or fails schema"):
            parse_grading(json.dumps({"overall_feedback": "ok"}), [1])

    def test_missing_overall_feedback_raises(self) -> None:
        payload = {"items": [{"item_id": 1, "score": 1.0, "critical_misconception": False, "feedback": "ok"}]}
        with pytest.raises(QuizGradingError):
            parse_grading(json.dumps(payload), [1])

    def test_mismatched_item_ids_raises(self) -> None:
        with pytest.raises(QuizGradingError, match="every quiz item exactly once"):
            parse_grading(json.dumps(_valid_payload([1, 2])), [1, 3])

    def test_empty_feedback_raises(self) -> None:
        payload = {
            "items": [{"item_id": 1, "score": 1.0, "critical_misconception": False, "feedback": "   "}],
            "overall_feedback": "ok",
        }
        with pytest.raises(QuizGradingError):
            parse_grading(json.dumps(payload), [1])


class TestPydanticValidation:
    """Pydantic schema validation catches bad data that manual parsing might miss."""

    def test_score_out_of_range_rejected(self) -> None:
        """Pydantic Field(ge=0, le=1) catches scores outside 0..1."""
        payload = {
            "items": [{"item_id": 1, "score": 1.5, "critical_misconception": False, "feedback": "ok"}],
            "overall_feedback": "done",
        }
        with pytest.raises(QuizGradingError, match="not valid JSON or fails schema"):
            parse_grading(json.dumps(payload), [1])

    def test_extra_fields_on_item_rejected(self) -> None:
        """Pydantic extra='forbid' catches unexpected fields on grading items."""
        payload = {
            "items": [
                {
                    "item_id": 1,
                    "score": 0.9,
                    "critical_misconception": False,
                    "feedback": "Good.",
                    "rogue": True,
                }
            ],
            "overall_feedback": "done",
        }
        with pytest.raises(QuizGradingError, match="not valid JSON or fails schema"):
            parse_grading(json.dumps(payload), [1])
