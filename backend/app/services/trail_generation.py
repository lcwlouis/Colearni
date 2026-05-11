"""Trail generation service: LLM → validate graph → persist in one transaction.

The GraphGenerator protocol is injectable; tests substitute a fake without any LLM calls.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.trail import TrailInsert
from backend.app.services.graph_validation import (
    GraphValidationError,
    RawGraph,
    RawNode,
)

if TYPE_CHECKING:
    from backend.app.agents.llm_client import LLMClient

_PROMPT_PATH = Path(__file__).parent.parent / "agents" / "prompts" / "trail_generation.v1.md"


class GenerationError(Exception):
    """Raised when the LLM fails to produce a usable graph after the repair attempt."""


@runtime_checkable
class GraphGenerator(Protocol):
    async def generate(self, topic: str, goal: str, target_depth: str) -> str:
        """Return raw JSON string for the graph."""
        ...

    async def repair(self, raw_json: str, error: str) -> str:
        """Given broken JSON and an error message, return corrected JSON string."""
        ...


def _load_prompt(topic: str, goal: str, target_depth: str) -> str:
    template = _PROMPT_PATH.read_text()
    template = template.split("---\n", 2)[-1].strip()  # strip front-matter
    return (
        template.replace("{{topic}}", topic)
        .replace("{{goal}}", goal)
        .replace("{{target_depth}}", target_depth)
    )


def _parse_graph(raw: str) -> RawGraph:
    """Parse and validate a JSON string into a RawGraph. Raises GraphValidationError."""
    # Strip accidental markdown fences
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GraphValidationError(f"LLM returned invalid JSON: {exc}") from exc
    return RawGraph.model_validate(data)


class LLMGraphGenerator:
    """LLMClient-backed graph generator. Provider wiring lives in LLMClient."""

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def generate(self, topic: str, goal: str, target_depth: str) -> str:
        prompt = _load_prompt(topic, goal, target_depth)
        return await self._client.chat([{"role": "user", "content": prompt}], temperature=0.4)

    async def repair(self, raw_json: str, error: str) -> str:
        repair_prompt = (
            "The following JSON concept graph failed validation with this error:\n"
            f"ERROR: {error}\n\n"
            "Fix the JSON so it passes validation. Return ONLY valid JSON, no explanation.\n\n"
            f"ORIGINAL JSON:\n{raw_json}"
        )
        return await self._client.chat(
            [{"role": "user", "content": repair_prompt}], temperature=0.2
        )


async def generate_and_store_trail(
    *,
    session: AsyncSession,
    generator: GraphGenerator,
    workspace_id: uuid.UUID,
    topic: str,
    goal: str,
    target_depth: str,
) -> tuple[Trail, list[ConceptNode], list[ConceptEdge]]:
    """Generate a trail + concept graph and persist everything in one transaction.

    Raises:
        LookupError: workspace_id not found.
        GenerationError: LLM failed after one repair attempt.
        GraphValidationError: graph still invalid after repair.
    """
    # Verify workspace exists
    result = await session.execute(select(Workspace).where(Workspace.id == workspace_id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise LookupError(f"Workspace {workspace_id} not found")

    # Generate graph — one repair attempt on failure
    raw = await generator.generate(topic, goal, target_depth)
    try:
        graph = _parse_graph(raw)
    except (GraphValidationError, Exception) as first_err:
        repaired = await generator.repair(raw, str(first_err))
        try:
            graph = _parse_graph(repaired)
        except Exception as second_err:
            raise GenerationError(
                f"LLM graph invalid after repair: {second_err}"
            ) from second_err

    # Build slug → ConceptNode map for edge resolution
    title = _title_from_graph(graph.nodes, topic)
    insert = TrailInsert(
        workspace_id=workspace_id,
        title=title,
        topic=topic,
        goal=goal,
        target_depth=target_depth,
    )

    trail = Trail(
        workspace_id=insert.workspace_id,
        title=insert.title,
        topic=insert.topic,
        goal=insert.goal,
        target_depth=insert.target_depth,
    )
    session.add(trail)
    await session.flush()  # get trail.id without committing

    slug_to_node: dict[str, ConceptNode] = {}
    nodes: list[ConceptNode] = []
    for raw_node in graph.nodes:
        node = ConceptNode(
            trail_id=trail.id,
            slug=raw_node.slug,
            title=raw_node.title,
            node_type=raw_node.node_type,
            concept_level=raw_node.concept_level,
            difficulty=raw_node.difficulty,
            bloom_level=raw_node.bloom_level,
            mastery_check_labels=raw_node.mastery_check_labels,
            metadata_json=raw_node.metadata_json,
        )
        session.add(node)
        nodes.append(node)
        slug_to_node[raw_node.slug] = node

    await session.flush()  # get node IDs

    edges: list[ConceptEdge] = []
    for raw_edge in graph.edges:
        edge = ConceptEdge(
            trail_id=trail.id,
            source_node_id=slug_to_node[raw_edge.source_slug].id,
            target_node_id=slug_to_node[raw_edge.target_slug].id,
            relation_type=raw_edge.relation_type,
        )
        session.add(edge)
        edges.append(edge)

    await session.commit()
    await session.refresh(trail)
    return trail, nodes, edges


def _title_from_graph(nodes: list[RawNode], fallback_topic: str) -> str:
    """Derive a trail title from the umbrella/topic node, or fall back to topic."""
    for level in ("umbrella", "topic"):
        for node in nodes:
            if node.concept_level == level:
                return node.title
    return fallback_topic.title()
