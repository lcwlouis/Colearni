"""Graph validation for LLM-generated concept graphs.

All validation runs before any DB writes. Raises GraphValidationError on failure.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from backend.app.schemas.types import (
    BloomLevel,
    ConceptLevel,
    Difficulty,
    NodeType,
    RelationType,
)

MAX_NODES = 30
MIN_NODES = 3


class GraphValidationError(ValueError):
    pass


class RawNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    title: str
    node_type: NodeType
    concept_level: ConceptLevel
    difficulty: Difficulty
    bloom_level: BloomLevel
    mastery_check_labels: list[str] = []
    metadata_json: dict = {}


class RawEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_slug: str
    target_slug: str
    relation_type: RelationType


class RawGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[RawNode]
    edges: list[RawEdge]

    @model_validator(mode="after")
    def _validate_graph(self) -> RawGraph:
        validate_graph(self.nodes, self.edges)
        return self


def validate_graph(nodes: list[RawNode], edges: list[RawEdge]) -> None:
    """Validate a raw concept graph.

    Raises GraphValidationError describing the first problem found.
    """
    # 1. Node count
    if len(nodes) < MIN_NODES:
        raise GraphValidationError(
            f"Graph must have at least {MIN_NODES} nodes, got {len(nodes)}"
        )
    if len(nodes) > MAX_NODES:
        raise GraphValidationError(
            f"Graph must have at most {MAX_NODES} nodes, got {len(nodes)}"
        )

    # 2. Unique slugs
    slugs: list[str] = [n.slug for n in nodes]
    slug_set: set[str] = set()
    for slug in slugs:
        if slug in slug_set:
            raise GraphValidationError(f"Duplicate node slug: {slug!r}")
        slug_set.add(slug)

    # 3. At least one umbrella or topic node (entry point)
    entry_levels = {"umbrella", "topic"}
    if not any(n.concept_level in entry_levels for n in nodes):
        raise GraphValidationError(
            "Graph must contain at least one umbrella or topic node as an entry point"
        )

    # 4. Edge slugs reference valid nodes
    for edge in edges:
        if edge.source_slug not in slug_set:
            raise GraphValidationError(
                f"Edge references unknown source_slug: {edge.source_slug!r}"
            )
        if edge.target_slug not in slug_set:
            raise GraphValidationError(
                f"Edge references unknown target_slug: {edge.target_slug!r}"
            )

    # 5. Prerequisite edges must be acyclic (DFS cycle detection)
    prereq_edges = [e for e in edges if e.relation_type == "prerequisite"]
    if prereq_edges:
        _assert_acyclic(list(slug_set), prereq_edges)


def _assert_acyclic(slugs: list[str], edges: list[RawEdge]) -> None:
    """DFS-based cycle detection on prerequisite edges.

    Raises GraphValidationError if a cycle is found.
    """
    adjacency: dict[str, list[str]] = {s: [] for s in slugs}
    for e in edges:
        adjacency[e.source_slug].append(e.target_slug)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {s: WHITE for s in slugs}

    def dfs(node: str) -> None:
        color[node] = GRAY
        for neighbor in adjacency[node]:
            if color[neighbor] == GRAY:
                raise GraphValidationError(
                    f"Prerequisite cycle detected involving node: {node!r}"
                )
            if color[neighbor] == WHITE:
                dfs(neighbor)
        color[node] = BLACK

    for slug in slugs:
        if color[slug] == WHITE:
            dfs(slug)
