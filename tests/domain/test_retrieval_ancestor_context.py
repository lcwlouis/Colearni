"""Tests for ancestor context injection helpers in retrieval_context."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from domain.chat.retrieval_context import (
    _build_ancestor_context_line,
    build_ancestor_context,
    build_hierarchy_path,
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


class TestBuildHierarchyPath:
    def test_correct_root_to_leaf_order(self):
        """Ancestors (parent → root) should be reversed to root → leaf, with current concept last."""
        session = MagicMock()
        ancestors = [
            {"concept_id": "20", "canonical_name": "Subtopic A", "description": "", "tier": "subtopic"},
            {"concept_id": "10", "canonical_name": "Topic X", "description": "", "tier": "topic"},
            {"concept_id": "1", "canonical_name": "Umbrella", "description": "", "tier": "umbrella"},
        ]
        with patch("domain.graph.explore.get_ancestor_chain", return_value=ancestors):
            result = build_hierarchy_path(
                session,
                workspace_id=1,
                concept_id=99,
                tier="granular",
                concept_name="Detail Z",
            )
        assert len(result) == 4
        assert result[0] == {"concept_id": 1, "name": "Umbrella", "tier": "umbrella"}
        assert result[1] == {"concept_id": 10, "name": "Topic X", "tier": "topic"}
        assert result[2] == {"concept_id": 20, "name": "Subtopic A", "tier": "subtopic"}
        assert result[3] == {"concept_id": 99, "name": "Detail Z", "tier": "granular"}

    def test_empty_list_when_no_concept_id(self):
        session = MagicMock()
        result = build_hierarchy_path(
            session, workspace_id=1, concept_id=None, tier="topic"
        )
        assert result == []

    def test_no_ancestors_still_includes_current_concept(self):
        """When no ancestors exist, the path should contain only the current concept."""
        session = MagicMock()
        with patch("domain.graph.explore.get_ancestor_chain", return_value=[]):
            result = build_hierarchy_path(
                session,
                workspace_id=1,
                concept_id=42,
                tier="topic",
                concept_name="Solo Topic",
            )
        assert result == [{"concept_id": 42, "name": "Solo Topic", "tier": "topic"}]

    def test_exception_returns_empty_list(self):
        session = MagicMock()
        with patch(
            "domain.graph.explore.get_ancestor_chain",
            side_effect=RuntimeError("db error"),
        ):
            result = build_hierarchy_path(
                session, workspace_id=1, concept_id=42, tier="subtopic"
            )
        assert result == []

    def test_single_ancestor(self):
        session = MagicMock()
        ancestors = [
            {"concept_id": "5", "canonical_name": "Parent", "description": "", "tier": "topic"},
        ]
        with patch("domain.graph.explore.get_ancestor_chain", return_value=ancestors):
            result = build_hierarchy_path(
                session,
                workspace_id=1,
                concept_id=15,
                tier="subtopic",
                concept_name="Child",
            )
        assert len(result) == 2
        assert result[0] == {"concept_id": 5, "name": "Parent", "tier": "topic"}
        assert result[1] == {"concept_id": 15, "name": "Child", "tier": "subtopic"}
