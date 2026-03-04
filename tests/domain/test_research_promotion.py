"""Tests for learning-gated candidate promotion (AR5.4)."""

from __future__ import annotations

from unittest.mock import MagicMock

from domain.research.promotion import (
    evaluate_candidate_for_promotion,
    promote_candidate,
    record_promotion_feedback,
)


class TestEvaluateCandidateForPromotion:
    """Test promotion decision logic."""

    def test_approved_promotes(self):
        d = evaluate_candidate_for_promotion(candidate_id=1, candidate_status="approved")
        assert d.action == "promote"
        assert d.is_promoting

    def test_pending_rejects(self):
        d = evaluate_candidate_for_promotion(candidate_id=2, candidate_status="pending")
        assert d.action == "reject"
        assert not d.is_promoting
        assert "'pending'" in d.reason

    def test_rejected_rejects(self):
        d = evaluate_candidate_for_promotion(candidate_id=3, candidate_status="rejected")
        assert d.action == "reject"

    def test_quiz_gate_not_passed(self):
        d = evaluate_candidate_for_promotion(
            candidate_id=4, candidate_status="approved",
            has_quiz_gate=True, quiz_passed=False,
        )
        assert d.action == "quiz_gate"
        assert d.requires_review_quiz
        assert d.is_promoting

    def test_quiz_gate_passed(self):
        d = evaluate_candidate_for_promotion(
            candidate_id=5, candidate_status="approved",
            has_quiz_gate=True, quiz_passed=True,
        )
        assert d.action == "promote"

    def test_no_quiz_gate_ignores_quiz_status(self):
        d = evaluate_candidate_for_promotion(
            candidate_id=6, candidate_status="approved",
            has_quiz_gate=False, quiz_passed=False,
        )
        assert d.action == "promote"


class TestPromoteCandidate:
    """Test the promote_candidate DB operation."""

    def test_promote_success(self):
        session = MagicMock()
        result_mock = MagicMock()
        result_mock.rowcount = 1
        session.execute.return_value = result_mock

        d = evaluate_candidate_for_promotion(candidate_id=1, candidate_status="approved")
        promoted = promote_candidate(session, candidate_id=1, workspace_id=10, decision=d)

        assert promoted
        session.execute.assert_called_once()
        session.commit.assert_called_once()

    def test_promote_no_matching_row(self):
        session = MagicMock()
        result_mock = MagicMock()
        result_mock.rowcount = 0
        session.execute.return_value = result_mock

        d = evaluate_candidate_for_promotion(candidate_id=1, candidate_status="approved")
        promoted = promote_candidate(session, candidate_id=1, workspace_id=10, decision=d)

        assert not promoted

    def test_non_promote_action_returns_false(self):
        session = MagicMock()
        d = evaluate_candidate_for_promotion(candidate_id=2, candidate_status="pending")
        promoted = promote_candidate(session, candidate_id=2, workspace_id=10, decision=d)

        assert not promoted
        session.execute.assert_not_called()

    def test_db_failure_returns_false(self):
        session = MagicMock()
        session.execute.side_effect = RuntimeError("DB error")

        d = evaluate_candidate_for_promotion(candidate_id=1, candidate_status="approved")
        promoted = promote_candidate(session, candidate_id=1, workspace_id=10, decision=d)

        assert not promoted


class TestRecordPromotionFeedback:
    """Test feedback recording."""

    def test_records_feedback(self):
        session = MagicMock()
        record_promotion_feedback(
            session, candidate_id=1, workspace_id=10, user_id=5, feedback="Good resource",
        )
        session.execute.assert_called_once()
        session.commit.assert_called_once()

    def test_failure_does_not_raise(self):
        session = MagicMock()
        session.execute.side_effect = RuntimeError("DB error")
        # Should not raise
        record_promotion_feedback(
            session, candidate_id=1, workspace_id=10, user_id=5, feedback="test",
        )
