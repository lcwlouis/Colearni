"""Unit tests for get_ancestor_chain() in domain/graph/explore.py."""
from __future__ import annotations

from unittest.mock import MagicMock

from domain.graph.explore import get_ancestor_chain


def _make_session(rows):
    """Build a minimal mock session that returns *rows* from .execute()."""
    row_mappings = []
    for r in rows:
        m = MagicMock()
        m.__getitem__ = lambda self, key, _r=r: _r[key]
        row_mappings.append(m)

    mappings_mock = MagicMock()
    mappings_mock.all.return_value = row_mappings

    execute_result = MagicMock()
    execute_result.mappings.return_value = mappings_mock

    session = MagicMock()
    session.execute.return_value = execute_result
    return session


class TestGetAncestorChainNoEdges:
    def test_returns_empty_list_when_no_rows(self):
        session = _make_session([])
        result = get_ancestor_chain(session, workspace_id=1, concept_id=42)
        assert result == []

    def test_execute_was_called(self):
        session = _make_session([])
        get_ancestor_chain(session, workspace_id=1, concept_id=42)
        session.execute.assert_called_once()


class TestGetAncestorChainWithRows:
    def _make_row(self, concept_id, canonical_name, description, hop_distance, tier=None):
        return {
            "concept_id": concept_id,
            "canonical_name": canonical_name,
            "description": description,
            "hop_distance": hop_distance,
            "tier": tier,
        }

    def test_returns_ancestors_in_order(self):
        rows = [
            self._make_row(10, "Algebra", "Branch of mathematics", 1, "topic"),
            self._make_row(20, "Mathematics", "Science of numbers", 2, "umbrella"),
        ]
        session = _make_session(rows)
        result = get_ancestor_chain(session, workspace_id=1, concept_id=5)

        assert len(result) == 2
        assert result[0]["concept_id"] == "10"
        assert result[0]["canonical_name"] == "Algebra"
        assert result[0]["description"] == "Branch of mathematics"
        assert result[0]["tier"] == "topic"
        assert result[1]["concept_id"] == "20"
        assert result[1]["canonical_name"] == "Mathematics"
        assert result[1]["tier"] == "umbrella"

    def test_tier_none_becomes_none(self):
        rows = [self._make_row(10, "Parent", "desc", 1, tier=None)]
        session = _make_session(rows)
        result = get_ancestor_chain(session, workspace_id=1, concept_id=5)
        assert result[0]["tier"] is None

    def test_description_none_becomes_empty_string(self):
        rows = [self._make_row(10, "Parent", None, 1)]
        session = _make_session(rows)
        result = get_ancestor_chain(session, workspace_id=1, concept_id=5)
        assert result[0]["description"] == ""

    def test_all_dict_keys_present(self):
        rows = [self._make_row(10, "Parent", "desc", 1, "topic")]
        session = _make_session(rows)
        result = get_ancestor_chain(session, workspace_id=1, concept_id=5)
        assert set(result[0].keys()) == {"concept_id", "canonical_name", "description", "tier"}


class TestGetAncestorChainMaxDepth:
    def test_max_depth_passed_to_query(self):
        session = _make_session([])
        get_ancestor_chain(session, workspace_id=1, concept_id=42, max_depth=5)
        call_kwargs = session.execute.call_args
        params = call_kwargs[0][1]
        assert params["max_depth"] == 5

    def test_default_max_depth_is_3(self):
        session = _make_session([])
        get_ancestor_chain(session, workspace_id=1, concept_id=42)
        call_kwargs = session.execute.call_args
        params = call_kwargs[0][1]
        assert params["max_depth"] == 3

    def test_max_depth_1_uses_correct_param(self):
        session = _make_session([])
        get_ancestor_chain(session, workspace_id=1, concept_id=42, max_depth=1)
        params = session.execute.call_args[0][1]
        assert params["max_depth"] == 1
