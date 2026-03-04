"""Tests for learner snapshot assembly service (AR4.2)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from domain.learner.assembler import (
    _mastery_score_to_level,
    _normalize_mastery,
    assemble_learner_snapshot,
)
from domain.learner.profile import LearnerProfileSnapshot


class TestNormalizeMastery:
    """Test mastery string normalization."""

    def test_none_returns_unseen(self):
        assert _normalize_mastery(None) == "unseen"

    def test_valid_values(self):
        for v in ("novice", "intermediate", "expert", "unseen"):
            assert _normalize_mastery(v) == v

    def test_case_insensitive(self):
        assert _normalize_mastery("Expert") == "expert"
        assert _normalize_mastery("NOVICE") == "novice"

    def test_invalid_returns_unseen(self):
        assert _normalize_mastery("garbage") == "unseen"
        assert _normalize_mastery("") == "unseen"


class TestMasteryScoreToLevel:
    """Test numeric score to categorical level mapping."""

    def test_zero_unseen(self):
        assert _mastery_score_to_level(0.0) == "unseen"

    def test_low_novice(self):
        assert _mastery_score_to_level(0.2) == "novice"

    def test_mid_intermediate(self):
        assert _mastery_score_to_level(0.6) == "intermediate"

    def test_high_expert(self):
        assert _mastery_score_to_level(0.9) == "expert"

    def test_boundary_05(self):
        assert _mastery_score_to_level(0.5) == "intermediate"

    def test_boundary_08(self):
        assert _mastery_score_to_level(0.8) == "expert"


def _mock_readiness_rows():
    return [
        {"concept_id": 1, "mastery_score": 0.9, "readiness_score": 0.85, "recommend_quiz": False},
        {"concept_id": 2, "mastery_score": 0.3, "readiness_score": 0.2, "recommend_quiz": True},
        {"concept_id": 3, "mastery_score": 0.6, "readiness_score": 0.55, "recommend_quiz": False},
    ]


def _mock_concept_row(canonical_name: str):
    row = MagicMock()
    row.canonical_name = canonical_name
    return row


class TestAssembleLearnerSnapshot:
    """Test the full assembly path."""

    @patch("domain.chat.session_memory.load_assessment_context", return_value="Quiz: 3/5 correct")
    @patch("adapters.db.graph.concepts.get_canonical_concept")
    @patch("domain.readiness.analyzer.analyze_workspace_readiness")
    def test_full_assembly(self, mock_readiness, mock_concept, mock_assessment):
        mock_readiness.return_value = _mock_readiness_rows()
        mock_concept.side_effect = lambda session, *, workspace_id, concept_id: {
            1: _mock_concept_row("Physics"),
            2: _mock_concept_row("Chemistry"),
            3: _mock_concept_row("Biology"),
        }.get(concept_id)

        session = MagicMock()
        snapshot = assemble_learner_snapshot(
            session, workspace_id=10, user_id=20, session_id=100,
        )

        assert isinstance(snapshot, LearnerProfileSnapshot)
        assert snapshot.workspace_id == 10
        assert snapshot.user_id == 20
        assert len(snapshot.topic_states) == 3
        assert snapshot.recent_session_summary == "Quiz: 3/5 correct"

        # Physics: 0.9 → expert
        physics = snapshot.topic_by_id(1)
        assert physics is not None
        assert physics.mastery_status == "expert"
        assert physics.is_strong

        # Chemistry: 0.3 → novice, recommend quiz
        chem = snapshot.topic_by_id(2)
        assert chem is not None
        assert chem.mastery_status == "novice"
        assert chem.is_weak
        assert chem.recommend_quiz

        # Biology: 0.6 → intermediate
        bio = snapshot.topic_by_id(3)
        assert bio is not None
        assert bio.mastery_status == "intermediate"

    @patch("domain.readiness.analyzer.analyze_workspace_readiness")
    def test_empty_readiness(self, mock_readiness):
        mock_readiness.return_value = []

        session = MagicMock()
        snapshot = assemble_learner_snapshot(
            session, workspace_id=10, user_id=20,
        )

        assert len(snapshot.topic_states) == 0
        assert snapshot.summary_text() == "No learner data available."

    @patch("domain.readiness.analyzer.analyze_workspace_readiness")
    def test_readiness_failure_safe(self, mock_readiness):
        mock_readiness.side_effect = RuntimeError("DB down")

        session = MagicMock()
        snapshot = assemble_learner_snapshot(
            session, workspace_id=10, user_id=20,
        )

        assert len(snapshot.topic_states) == 0
        assert isinstance(snapshot, LearnerProfileSnapshot)

    @patch("adapters.db.graph.concepts.get_canonical_concept")
    @patch("domain.readiness.analyzer.analyze_workspace_readiness")
    def test_missing_concept_name_fallback(self, mock_readiness, mock_concept):
        mock_readiness.return_value = [
            {"concept_id": 99, "mastery_score": 0.5, "readiness_score": 0.4, "recommend_quiz": False},
        ]
        mock_concept.return_value = None  # concept not found

        session = MagicMock()
        snapshot = assemble_learner_snapshot(
            session, workspace_id=10, user_id=20,
        )

        assert len(snapshot.topic_states) == 1
        assert snapshot.topic_states[0].canonical_name == "concept-99"

    def test_no_session_id_empty_summary(self):
        """When session_id is None, summary should be empty."""
        with patch("domain.readiness.analyzer.analyze_workspace_readiness", return_value=[]):
            session = MagicMock()
            snapshot = assemble_learner_snapshot(
                session, workspace_id=10, user_id=20, session_id=None,
            )
            assert snapshot.recent_session_summary == ""

    @patch("domain.chat.session_memory.load_assessment_context", side_effect=RuntimeError("fail"))
    @patch("domain.readiness.analyzer.analyze_workspace_readiness", return_value=[])
    def test_session_summary_failure_safe(self, _mock_readiness, _mock_assessment):
        session = MagicMock()
        snapshot = assemble_learner_snapshot(
            session, workspace_id=10, user_id=20, session_id=100,
        )
        assert snapshot.recent_session_summary == ""

    @patch("adapters.db.graph.concepts.get_canonical_concept")
    @patch("domain.readiness.analyzer.analyze_workspace_readiness")
    def test_derived_properties(self, mock_readiness, mock_concept):
        mock_readiness.return_value = _mock_readiness_rows()
        mock_concept.side_effect = lambda session, *, workspace_id, concept_id: {
            1: _mock_concept_row("Physics"),
            2: _mock_concept_row("Chemistry"),
            3: _mock_concept_row("Biology"),
        }.get(concept_id)

        session = MagicMock()
        snapshot = assemble_learner_snapshot(
            session, workspace_id=10, user_id=20,
        )

        assert len(snapshot.weak_topics) == 1  # Chemistry (novice)
        assert len(snapshot.strong_topics) == 1  # Physics (expert, high readiness)
        assert len(snapshot.current_frontier) == 1  # Biology (intermediate)
        assert len(snapshot.review_queue) == 1  # Chemistry (recommend_quiz)
