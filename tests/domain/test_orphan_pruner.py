"""Unit tests for orphan graph pruning (S44)."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

from domain.graph.orphan_pruner import (
    find_orphan_concept_ids,
    find_orphan_edge_ids,
    prune_orphan_graph_nodes,
)


def _mock_session(*, orphan_concept_ids=None, orphan_edge_ids=None):
    """Build a mock Session that returns specified orphan IDs."""
    session = MagicMock()
    orphan_concept_ids = orphan_concept_ids or []
    orphan_edge_ids = orphan_edge_ids or []

    call_count = {"n": 0}
    concept_query_marker = "concepts_canon"
    edge_query_marker = "edges_canon"

    def _side_effect(stmt, params=None):
        result = MagicMock()
        sql_text = str(stmt)

        if "DELETE" in sql_text:
            result.rowcount = len(orphan_concept_ids) if concept_query_marker in sql_text else len(orphan_edge_ids)
            return result

        # SELECT queries for finding orphans
        if concept_query_marker in sql_text and "NOT EXISTS" in sql_text:
            result.scalars.return_value.all.return_value = orphan_concept_ids
        elif edge_query_marker in sql_text and "NOT EXISTS" in sql_text:
            result.scalars.return_value.all.return_value = orphan_edge_ids
        else:
            result.scalars.return_value.all.return_value = []
        return result

    session.execute.side_effect = _side_effect
    return session


def test_find_orphan_concept_ids_empty():
    session = _mock_session(orphan_concept_ids=[])
    result = find_orphan_concept_ids(session, workspace_id=1)
    assert result == []


def test_find_orphan_concept_ids_returns_ids():
    session = _mock_session(orphan_concept_ids=[10, 20, 30])
    result = find_orphan_concept_ids(session, workspace_id=1)
    assert result == [10, 20, 30]


def test_find_orphan_edge_ids_empty():
    session = _mock_session(orphan_edge_ids=[])
    result = find_orphan_edge_ids(session, workspace_id=1)
    assert result == []


def test_find_orphan_edge_ids_returns_ids():
    session = _mock_session(orphan_edge_ids=[5, 15])
    result = find_orphan_edge_ids(session, workspace_id=1)
    assert result == [5, 15]


def test_prune_no_orphans():
    """When no orphans exist, nothing is deleted."""
    session = _mock_session(orphan_concept_ids=[], orphan_edge_ids=[])
    result = prune_orphan_graph_nodes(session, workspace_id=1)
    assert result["pruned_concepts"] == 0
    assert result["pruned_edges"] == 0


@patch("domain.graph.orphan_pruner.find_orphan_edge_ids", return_value=[5, 15])
@patch("domain.graph.orphan_pruner.find_orphan_concept_ids", return_value=[])
def test_prune_edges_only(mock_concepts, mock_edges):
    session = MagicMock()
    delete_result = MagicMock()
    delete_result.rowcount = 2
    session.execute.return_value = delete_result

    result = prune_orphan_graph_nodes(session, workspace_id=1)
    assert result["pruned_edges"] == 2
    assert result["pruned_concepts"] == 0


@patch("domain.graph.orphan_pruner.find_orphan_edge_ids", return_value=[])
@patch("domain.graph.orphan_pruner.find_orphan_concept_ids", return_value=[10, 20])
def test_prune_concepts_only(mock_concepts, mock_edges):
    session = MagicMock()
    delete_result = MagicMock()
    delete_result.rowcount = 2
    session.execute.return_value = delete_result

    result = prune_orphan_graph_nodes(session, workspace_id=1)
    assert result["pruned_concepts"] == 2
    # Edges deletion also runs (cascading edges referencing orphan concepts)
    assert session.execute.call_count >= 2


@patch("domain.graph.orphan_pruner.find_orphan_edge_ids", return_value=[5])
@patch("domain.graph.orphan_pruner.find_orphan_concept_ids", return_value=[10])
def test_prune_both_concepts_and_edges(mock_concepts, mock_edges):
    session = MagicMock()
    delete_result = MagicMock()
    delete_result.rowcount = 1
    session.execute.return_value = delete_result

    result = prune_orphan_graph_nodes(session, workspace_id=1)
    assert result["pruned_concepts"] == 1
    assert result["pruned_edges"] == 1


def test_prune_returns_correct_summary():
    """Verify the return dict schema."""
    session = _mock_session(orphan_concept_ids=[], orphan_edge_ids=[])
    result = prune_orphan_graph_nodes(session, workspace_id=1)
    assert "pruned_concepts" in result
    assert "pruned_edges" in result
    assert isinstance(result["pruned_concepts"], int)
    assert isinstance(result["pruned_edges"], int)
