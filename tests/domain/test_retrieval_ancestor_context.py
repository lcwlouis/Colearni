"""Tests for ancestor context injection helpers in retrieval_context."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from domain.chat.retrieval_context import (
    _build_ancestor_context_line,
    build_ancestor_context,
)


class TestBuildAncestorContextLine:
    def test_empty_list_returns_empty_string(self):
        assert _build_ancestor_context_line([]) == ""

    def test_single_ancestor(self):
        ancestors = [{"canonical_name": "Machine Learning", "concept_id": "1", "description": ""}]
        result = _build_ancestor_context_line(ancestors)
        assert result == "Concept hierarchy (from parent to root): Machine Learning"

    def test_multiple_ancestors_joined_with_arrow(self):
        ancestors = [
            {"canonical_name": "Gradient Descent", "concept_id": "2", "description": ""},
            {"canonical_name": "Optimization", "concept_id": "3", "description": ""},
            {"canonical_name": "Machine Learning", "concept_id": "1", "description": ""},
        ]
        result = _build_ancestor_context_line(ancestors)
        assert result == (
            "Concept hierarchy (from parent to root): "
            "Gradient Descent → Optimization → Machine Learning"
        )


class TestBuildAncestorContext:
    def test_none_tier_skips_chain_call(self):
        session = MagicMock()
        with patch("domain.graph.explore.get_ancestor_chain") as mock_chain:
            result = build_ancestor_context(
                session, workspace_id=1, concept_id=42, tier=None
            )
        mock_chain.assert_not_called()
        assert result == ""

    def test_non_hierarchical_tier_skips_chain_call(self):
        session = MagicMock()
        with patch("domain.graph.explore.get_ancestor_chain") as mock_chain:
            result = build_ancestor_context(
                session, workspace_id=1, concept_id=42, tier="core"
            )
        mock_chain.assert_not_called()
        assert result == ""

    def test_subtopic_tier_calls_chain(self):
        session = MagicMock()
        ancestors = [{"canonical_name": "Parent Topic", "concept_id": "10", "description": ""}]
        with patch(
            "domain.graph.explore.get_ancestor_chain", return_value=ancestors
        ) as mock_chain:
            result = build_ancestor_context(
                session, workspace_id=1, concept_id=99, tier="subtopic"
            )
        mock_chain.assert_called_once_with(session, workspace_id=1, concept_id=99)
        assert result == "Concept hierarchy (from parent to root): Parent Topic"

    def test_granular_tier_calls_chain(self):
        session = MagicMock()
        ancestors = [{"canonical_name": "Sub", "concept_id": "5", "description": ""}]
        with patch(
            "domain.graph.explore.get_ancestor_chain", return_value=ancestors
        ) as mock_chain:
            result = build_ancestor_context(
                session, workspace_id=2, concept_id=77, tier="granular"
            )
        mock_chain.assert_called_once()
        assert "Sub" in result

    def test_empty_ancestor_chain_returns_empty(self):
        session = MagicMock()
        with patch("domain.graph.explore.get_ancestor_chain", return_value=[]):
            result = build_ancestor_context(
                session, workspace_id=1, concept_id=42, tier="subtopic"
            )
        assert result == ""

    def test_exception_from_chain_returns_empty(self):
        session = MagicMock()
        with patch(
            "domain.graph.explore.get_ancestor_chain", side_effect=RuntimeError("db error")
        ):
            result = build_ancestor_context(
                session, workspace_id=1, concept_id=42, tier="subtopic"
            )
        assert result == ""
