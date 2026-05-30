"""Trail generation service: LLM → validate graph → persist in one transaction.

The GraphGenerator protocol is injectable; tests substitute a fake without any LLM calls.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.prompts import prompt_registry
from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.concept import ConceptEdgeRead, ConceptNodeRead
from backend.app.schemas.trail import (
    TrailGenerateResponse,
    TrailGraphRead,
    TrailInsert,
    TrailRead,
)
from backend.app.schemas.types import TargetDepth
from backend.app.services.graph_validation import (
    GraphValidationError,
    RawGraph,
    RawNode,
    validate_graph,
)
from backend.app.settings import settings

if TYPE_CHECKING:
    from backend.app.agents.llm_client import LLMClient

_MIN_GENERATION_MAX_TOKENS = 4096
_MAX_GENERATION_MAX_TOKENS = 16000
_REPAIR_MAX_TOKENS = 12000


class GenerationError(Exception):
    """Raised when the LLM fails to produce a usable graph after the repair attempt."""


@runtime_checkable
class GraphGenerator(Protocol):
    async def generate(
        self, topic: str, goal: str, target_depth: TargetDepth, max_nodes: int = 40
    ) -> str:
        """Return raw JSON string for the graph."""
        ...

    def generate_stream(
        self, topic: str, goal: str, target_depth: TargetDepth, max_nodes: int = 40
    ) -> AsyncIterator[tuple[str, str]]:
        """Yield (kind, chunk) tuples where kind is 'text' or 'thinking'."""
        ...

    async def repair(self, raw_json: str, error: str) -> str:
        """Given broken JSON and an error message, return corrected JSON string."""
        ...


def _load_prompt(topic: str, goal: str, target_depth: TargetDepth, max_nodes: int) -> str:
    return prompt_registry.render(
        "trail_generation",
        {
            "topic": topic,
            "goal": goal,
            "target_depth": target_depth,
            "max_nodes": max_nodes,
        },
        version=1,
    )


def _parse_graph(raw: str, *, max_nodes: int = 40) -> RawGraph:
    """Parse and validate a JSON string into a RawGraph. Raises GraphValidationError."""
    # Strip accidental markdown fences
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GraphValidationError(f"LLM returned invalid JSON: {exc}") from exc
    graph = RawGraph.model_validate(data)
    validate_graph(graph.nodes, graph.edges, max_nodes=max_nodes)
    return graph


class LLMGraphGenerator:
    """LLMClient-backed graph generator. Provider wiring lives in LLMClient."""

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    async def generate(
        self, topic: str, goal: str, target_depth: TargetDepth, max_nodes: int = 40
    ) -> str:
        prompt = _load_prompt(topic, goal, target_depth, max_nodes)
        return await self._client.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=_generation_max_tokens(max_nodes),
        )

    async def generate_stream(
        self, topic: str, goal: str, target_depth: TargetDepth, max_nodes: int = 40
    ) -> AsyncIterator[tuple[str, str]]:
        prompt = _load_prompt(topic, goal, target_depth, max_nodes)
        async for kind, chunk in self._client.chat_stream_tagged(
            [{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=_generation_max_tokens(max_nodes),
        ):
            yield kind, chunk

    async def repair(self, raw_json: str, error: str) -> str:
        repair_prompt = (
            "The following JSON concept graph failed validation with this error:\n"
            f"ERROR: {error}\n\n"
            "Fix the JSON so it passes validation. Return ONLY valid JSON, no explanation.\n\n"
            f"ORIGINAL JSON:\n{raw_json}"
        )
        return await self._client.chat(
            [{"role": "user", "content": repair_prompt}],
            temperature=0.2,
            max_tokens=_REPAIR_MAX_TOKENS,
        )


# ------------------------------------------------------------------
# Private helpers shared by the blocking and streaming paths
# ------------------------------------------------------------------


async def _lookup_workspace(session: AsyncSession, workspace_id: uuid.UUID) -> None:
    """Raises LookupError if the workspace does not exist."""
    result = await session.execute(select(Workspace).where(Workspace.id == workspace_id))
    if result.scalar_one_or_none() is None:
        raise LookupError(f"Workspace {workspace_id} not found")


async def _validate_with_repair(raw: str, *, max_nodes: int, generator: GraphGenerator) -> RawGraph:
    """Parse and validate raw JSON with one repair attempt on failure.

    Raises GenerationError if repair fails or graph is still invalid after repair.
    """
    try:
        return _parse_graph(raw, max_nodes=max_nodes)
    except Exception as first_err:
        try:
            repaired = await generator.repair(raw, str(first_err))
        except Exception as exc:
            raise GenerationError(f"LLM repair call failed: {exc}") from exc
        try:
            return _parse_graph(repaired, max_nodes=max_nodes)
        except Exception as second_err:
            raise GenerationError(f"LLM graph invalid after repair: {second_err}") from second_err


async def _persist_trail(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    topic: str,
    goal: str,
    target_depth: TargetDepth,
    graph: RawGraph,
    prior_knowledge: str | None = None,
) -> tuple[Trail, list[ConceptNode], list[ConceptEdge]]:
    """Persist the Trail, ConceptNodes and ConceptEdges in a single transaction."""
    try:
        title = _title_from_graph(graph.nodes, topic)
        insert = TrailInsert(
            workspace_id=workspace_id,
            title=title,
            topic=topic,
            goal=goal,
            target_depth=target_depth,
            prior_knowledge=prior_knowledge,
        )

        trail = Trail(
            workspace_id=insert.workspace_id,
            title=insert.title,
            topic=insert.topic,
            goal=insert.goal,
            target_depth=insert.target_depth,
            prior_knowledge=insert.prior_knowledge,
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
    except Exception:
        await session.rollback()
        raise


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


async def generate_and_store_trail(
    *,
    session: AsyncSession,
    generator: GraphGenerator,
    workspace_id: uuid.UUID,
    topic: str,
    goal: str,
    target_depth: TargetDepth,
    max_nodes: int = 40,
    prior_knowledge: str | None = None,
) -> tuple[Trail, list[ConceptNode], list[ConceptEdge]]:
    """Generate a trail + concept graph and persist everything in one transaction.

    Raises:
        LookupError: workspace_id not found.
        GenerationError: LLM call failed, repair call failed, or graph invalid after repair.
    """
    await _lookup_workspace(session, workspace_id)

    try:
        raw = await generator.generate(topic, goal, target_depth, max_nodes)
    except Exception as exc:
        raise GenerationError(f"LLM call failed: {exc}") from exc

    graph = await _validate_with_repair(raw, max_nodes=max_nodes, generator=generator)
    return await _persist_trail(
        session, workspace_id, topic, goal, target_depth, graph, prior_knowledge
    )


async def stream_generate_trail_events(
    *,
    session: AsyncSession,
    generator: GraphGenerator,
    workspace_id: uuid.UUID,
    topic: str,
    goal: str,
    target_depth: TargetDepth,
    max_nodes: int = 40,
    prior_knowledge: str | None = None,
) -> AsyncIterator[str]:
    """Yield SSE events for trail generation, streaming LLM tokens as delta events."""

    # 1. Verify workspace before doing any LLM work.
    try:
        await _lookup_workspace(session, workspace_id)
    except LookupError as exc:
        yield _sse("error", {"error": {"code": "not_found", "message": str(exc), "details": {}}})
        return

    yield _sse("progress", {"message": f'Generating concept graph for "{topic}"...'})

    # 2. Stream LLM tokens, accumulating completion text for validation. Some
    # reasoning-capable providers can emit useful JSON in reasoning with little
    # or no final completion, so keep reasoning as a fallback instead of losing it.
    raw_chunks: list[str] = []
    reasoning_chunks: list[str] = []
    try:
        async for kind, chunk in generator.generate_stream(topic, goal, target_depth, max_nodes):
            if kind == "thinking":
                reasoning_chunks.append(chunk)
                yield _sse("thinking", {"text": chunk})
            else:
                raw_chunks.append(chunk)
                yield _sse("delta", {"text": chunk})
    except Exception as exc:
        yield _sse(
            "error",
            {"error": {"code": "llm_error", "message": f"LLM call failed: {exc}", "details": {}}},
        )
        return

    raw = "".join(raw_chunks).strip()
    if not raw:
        raw = "".join(reasoning_chunks).strip()
        yield _sse(
            "progress",
            {"message": "No completion text received; validating reasoning output..."},
        )

    # 3. Validate — one repair attempt on failure.
    yield _sse("progress", {"message": "Validating graph structure..."})
    try:
        graph = _parse_graph(raw, max_nodes=max_nodes)
    except Exception as first_err:
        yield _sse("progress", {"message": "Graph needs repair — asking LLM to fix it..."})
        try:
            repaired = await generator.repair(raw, str(first_err))
        except Exception as exc:
            yield _sse(
                "error",
                {
                    "error": {
                        "code": "llm_error",
                        "message": f"LLM repair call failed: {exc}",
                        "details": {},
                    }
                },
            )
            return
        try:
            graph = _parse_graph(repaired, max_nodes=max_nodes)
        except Exception as second_err:
            yield _sse(
                "error",
                {
                    "error": {
                        "code": "llm_error",
                        "message": f"LLM graph invalid after repair: {second_err}",
                        "details": {},
                    }
                },
            )
            return

    # 4. Persist.
    yield _sse("progress", {"message": f"Saving Trail with {len(graph.nodes)} concepts..."})
    try:
        trail, nodes, edges = await _persist_trail(
            session, workspace_id, topic, goal, target_depth, graph, prior_knowledge
        )
    except Exception as exc:
        yield _sse(
            "error",
            {"error": {"code": "db_error", "message": str(exc), "details": {}}},
        )
        return

    # 5. Done.
    trail_read = TrailRead.model_validate(trail)
    trail_read.node_count = len(nodes)
    trail_read.edge_count = len(edges)
    yield _sse(
        "done",
        TrailGenerateResponse(
            trail=trail_read,
            graph=_graph_read(nodes, edges),
        ).model_dump(mode="json"),
    )


def _generation_max_tokens(max_nodes: int) -> int:
    return min(
        _MAX_GENERATION_MAX_TOKENS,
        max(_MIN_GENERATION_MAX_TOKENS, max_nodes * settings.llm_generation_tokens_per_node),
    )


def _graph_read(nodes: list[ConceptNode], edges: list[ConceptEdge]) -> TrailGraphRead:
    return TrailGraphRead(
        nodes=[ConceptNodeRead.model_validate(node) for node in nodes],
        edges=[ConceptEdgeRead.model_validate(edge) for edge in edges],
    )


def _title_from_graph(nodes: list[RawNode], fallback_topic: str) -> str:
    """Derive a trail title from the umbrella/topic node, or fall back to topic."""
    for level in ("umbrella", "topic"):
        for node in nodes:
            if node.concept_level == level:
                return node.title
    return fallback_topic.title()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"
