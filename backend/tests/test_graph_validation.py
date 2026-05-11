"""Tests for graph_validation.py."""

import pytest

from backend.app.services.graph_validation import (
    GraphValidationError,
    RawEdge,
    RawNode,
    validate_graph,
)


def _node(slug: str, level: str = "topic", **kw) -> RawNode:
    return RawNode(
        slug=slug,
        title=slug.replace("-", " ").title(),
        node_type=kw.get("node_type", "concept"),
        concept_level=level,
        difficulty=kw.get("difficulty", "beginner"),
        bloom_level=kw.get("bloom_level", "understand"),
    )


def _edge(src: str, tgt: str, rel: str = "contains") -> RawEdge:
    return RawEdge(source_slug=src, target_slug=tgt, relation_type=rel)


MINIMAL_NODES = [_node("root", "umbrella"), _node("a"), _node("b")]


def test_valid_graph_passes():
    validate_graph(MINIMAL_NODES, [_edge("root", "a"), _edge("root", "b")])


def test_duplicate_slug_raises():
    nodes = [_node("root", "umbrella"), _node("a"), _node("a")]
    with pytest.raises(GraphValidationError, match="Duplicate"):
        validate_graph(nodes, [])


def test_bad_concept_level_raises():
    with pytest.raises(Exception):
        _node("bad", level="not-a-level")  # Pydantic rejects it


def test_missing_slug_in_edge_raises():
    with pytest.raises(GraphValidationError, match="unknown source_slug"):
        validate_graph(MINIMAL_NODES, [_edge("nonexistent", "a")])


def test_prerequisite_cycle_raises():
    nodes = [_node("root", "umbrella"), _node("a"), _node("b")]
    edges = [
        _edge("a", "b", "prerequisite"),
        _edge("b", "a", "prerequisite"),
    ]
    with pytest.raises(GraphValidationError, match="cycle"):
        validate_graph(nodes, edges)


def test_too_large_graph_raises():
    nodes = [_node(f"n{i}", "topic" if i == 0 else "subtopic") for i in range(31)]
    with pytest.raises(GraphValidationError, match="at most 30"):
        validate_graph(nodes, [])


def test_too_small_graph_raises():
    nodes = [_node("root", "umbrella"), _node("a")]
    with pytest.raises(GraphValidationError, match="at least 3"):
        validate_graph(nodes, [])


def test_no_entry_node_raises():
    nodes = [_node("a", "subtopic"), _node("b", "granular"), _node("c", "granular")]
    with pytest.raises(GraphValidationError, match="entry point"):
        validate_graph(nodes, [])


def test_all_relation_types_valid():
    nodes = [_node("root", "umbrella"), _node("a"), _node("b"), _node("c"), _node("d")]
    edges = [
        _edge("root", "a", "prerequisite"),
        _edge("root", "b", "contains"),
        _edge("root", "c", "application"),
        _edge("root", "d", "related"),
    ]
    validate_graph(nodes, edges)  # should not raise
