"""Tests for graph_validation.py."""

from typing import cast

import pytest

from backend.app.schemas.types import ConceptLevel, RelationType
from backend.app.services.graph_validation import (
    GraphValidationError,
    RawEdge,
    RawNode,
    validate_graph,
)


def _node(slug: str, level: ConceptLevel = "topic", **kw) -> RawNode:
    return RawNode(
        slug=slug,
        title=slug.replace("-", " ").title(),
        node_type=kw.get("node_type", "concept"),
        concept_level=level,
        difficulty=kw.get("difficulty", "beginner"),
        bloom_level=kw.get("bloom_level", "understand"),
    )


def _edge(src: str, tgt: str, rel: RelationType = "contains") -> RawEdge:
    return RawEdge(source_slug=src, target_slug=tgt, relation_type=rel)


def _make_nodes(n: int = 10) -> list[RawNode]:
    """Return n valid nodes: 1 umbrella root + (n-1) topic nodes."""
    return [_node("root", "umbrella")] + [_node(f"n{i}") for i in range(n - 1)]


MINIMAL_NODES = _make_nodes(10)


def test_valid_graph_passes():
    validate_graph(MINIMAL_NODES, [_edge("root", "n0"), _edge("root", "n1")])


def test_duplicate_slug_raises():
    nodes = _make_nodes(10)  # slugs: root, n0..n8
    nodes.append(_node("n0"))  # duplicate
    with pytest.raises(GraphValidationError, match="Duplicate"):
        validate_graph(nodes, [])


def test_duplicate_title_raises():
    nodes = _make_nodes(10)  # includes _node("root", "umbrella") with title "Root"
    # Replace last node with one whose normalized title matches "Root"
    nodes[-1] = RawNode(
        slug="dup-title-node",
        title=" root ",  # strip().lower() == "root"
        node_type="concept",
        concept_level="subtopic",
        difficulty="beginner",
        bloom_level="understand",
    )
    with pytest.raises(GraphValidationError, match="[Dd]uplicate.*itle"):
        validate_graph(nodes, [])


def test_bad_concept_level_raises():
    with pytest.raises(Exception):
        _node("bad", level=cast(ConceptLevel, "not-a-level"))  # Pydantic rejects it


def test_missing_slug_in_edge_raises():
    with pytest.raises(GraphValidationError, match="unknown source_slug"):
        validate_graph(MINIMAL_NODES, [_edge("nonexistent", "n0")])


def test_prerequisite_cycle_raises():
    nodes = _make_nodes(10)
    edges = [
        _edge("n0", "n1", "prerequisite"),
        _edge("n1", "n0", "prerequisite"),
    ]
    with pytest.raises(GraphValidationError, match="cycle"):
        validate_graph(nodes, edges)


def test_too_large_graph_raises():
    nodes = [_node(f"n{i}", "topic" if i == 0 else "subtopic") for i in range(31)]
    with pytest.raises(GraphValidationError, match="at most 30"):
        validate_graph(nodes, [])


def test_larger_graph_allowed_when_max_nodes_increased():
    nodes = [_node(f"n{i}", "topic" if i == 0 else "subtopic") for i in range(60)]
    validate_graph(nodes, [], max_nodes=60)


def test_graph_max_nodes_cannot_exceed_absolute_bound():
    nodes = [_node(f"n{i}", "topic" if i == 0 else "subtopic") for i in range(101)]
    with pytest.raises(GraphValidationError, match="cannot exceed 100"):
        validate_graph(nodes, [], max_nodes=101)


def test_too_small_graph_raises():
    nodes = _make_nodes(9)  # 9 nodes, below minimum of 10
    with pytest.raises(GraphValidationError, match="at least 10"):
        validate_graph(nodes, [])


def test_no_entry_node_raises():
    nodes = [_node(f"n{i}", "subtopic" if i < 5 else "granular") for i in range(10)]
    with pytest.raises(GraphValidationError, match="entry point"):
        validate_graph(nodes, [])


def test_all_relation_types_valid():
    nodes = _make_nodes(10)  # root + n0..n8
    edges = [
        _edge("root", "n0", "prerequisite"),
        _edge("root", "n1", "contains"),
        _edge("root", "n2", "application"),
        _edge("root", "n3", "related"),
    ]
    validate_graph(nodes, edges)  # should not raise
