"""Service-level tests for trail_generation.py (no HTTP, no real LLM)."""

import json
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.models.base import Base
from backend.app.models.concept import ConceptEdge, ConceptNode  # noqa: F401
from backend.app.models.source import ConceptSourceLink, SourceRecord  # noqa: F401
from backend.app.models.trail import Trail  # noqa: F401
from backend.app.models.workspace import Workspace
from backend.app.services.trail_generation import (
    GenerationError,
    generate_and_store_trail,
    stream_generate_trail_events,
)


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


def _minimal_graph_json(topic: str = "Math") -> str:
    """Valid 10-node, 9-edge concept graph for use in tests."""
    subtopics = [
        ("arithmetic", "Arithmetic"),
        ("algebra", "Algebra"),
        ("geometry", "Geometry"),
        ("statistics", "Statistics"),
        ("calculus", "Calculus"),
        ("number-theory", "Number Theory"),
        ("logic", "Logic"),
        ("set-theory", "Set Theory"),
        ("probability", "Probability"),
    ]
    nodes = [
        {
            "slug": "math-root",
            "title": topic,
            "node_type": "concept",
            "concept_level": "umbrella",
            "difficulty": "beginner",
            "bloom_level": "understand",
            "mastery_check_labels": [],
            "metadata_json": {},
        }
    ] + [
        {
            "slug": slug,
            "title": title,
            "node_type": "concept",
            "concept_level": "topic",
            "difficulty": "beginner",
            "bloom_level": "remember",
            "mastery_check_labels": [],
            "metadata_json": {},
        }
        for slug, title in subtopics
    ]
    edges = [
        {"source_slug": "math-root", "target_slug": slug, "relation_type": "contains"}
        for slug, _ in subtopics
    ]
    return json.dumps({"nodes": nodes, "edges": edges})


def _graph_json(node_count: int, topic: str = "Math") -> str:
    nodes = [
        {
            "slug": "math-root",
            "title": topic,
            "node_type": "concept",
            "concept_level": "umbrella",
            "difficulty": "beginner",
            "bloom_level": "understand",
            "mastery_check_labels": [],
            "metadata_json": {},
        }
    ] + [
        {
            "slug": f"n{i}",
            "title": f"Node {i}",
            "node_type": "concept",
            "concept_level": "subtopic",
            "difficulty": "beginner",
            "bloom_level": "understand",
            "mastery_check_labels": [],
            "metadata_json": {},
        }
        for i in range(node_count - 1)
    ]
    edges = [
        {"source_slug": "math-root", "target_slug": f"n{i}", "relation_type": "contains"}
        for i in range(node_count - 1)
    ]
    return json.dumps({"nodes": nodes, "edges": edges})


class ReasoningOnlyGenerator:
    def __init__(self, reasoning_json: str):
        self._reasoning_json = reasoning_json

    async def generate(self, topic: str, goal: str, target_depth: str, max_nodes: int = 40) -> str:
        return ""

    async def generate_stream(self, topic: str, goal: str, target_depth: str, max_nodes: int = 40):
        midpoint = len(self._reasoning_json) // 2
        yield ("thinking", self._reasoning_json[:midpoint])
        yield ("thinking", self._reasoning_json[midpoint:])

    async def repair(self, raw_json: str, error: str) -> str:
        return raw_json


class FakeGenerator:
    def __init__(
        self,
        json_str: str,
        repair_json_str: str | None = None,
        *,
        raise_on_generate: bool = False,
    ):
        self._json = json_str
        self._repair = repair_json_str
        self._raise_on_generate = raise_on_generate
        self.repair_called = False
        self.max_nodes_seen: int | None = None

    async def generate(self, topic: str, goal: str, target_depth: str, max_nodes: int = 40) -> str:
        self.max_nodes_seen = max_nodes
        if self._raise_on_generate:
            raise RuntimeError("Provider connection failed")
        return self._json

    async def generate_stream(self, topic: str, goal: str, target_depth: str, max_nodes: int = 40):
        self.max_nodes_seen = max_nodes
        if self._raise_on_generate:
            raise RuntimeError("Provider connection failed")
        chunk_size = max(1, len(self._json) // 4)
        for i in range(0, len(self._json), chunk_size):
            yield ("text", self._json[i : i + chunk_size])

    async def repair(self, raw_json: str, error: str) -> str:
        self.repair_called = True
        if self._repair is not None:
            return self._repair
        return self._json


async def test_persists_prior_knowledge_when_provided(db_session: AsyncSession):
    ws = Workspace(name="Prior Knowledge WS")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    generator = FakeGenerator(_minimal_graph_json())
    trail, _, _ = await generate_and_store_trail(
        session=db_session,
        generator=generator,
        workspace_id=ws.id,
        topic="Math",
        goal="Learn basics",
        target_depth="understand",
        prior_knowledge="I know arithmetic but not algebra.",
    )

    assert trail.prior_knowledge == "I know arithmetic but not algebra."


async def test_prior_knowledge_defaults_to_none(db_session: AsyncSession):
    ws = Workspace(name="No Prior Knowledge WS")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    generator = FakeGenerator(_minimal_graph_json())
    trail, _, _ = await generate_and_store_trail(
        session=db_session,
        generator=generator,
        workspace_id=ws.id,
        topic="Math",
        goal="Learn basics",
        target_depth="understand",
    )

    assert trail.prior_knowledge is None


async def test_stream_persists_prior_knowledge(db_session: AsyncSession):
    ws = Workspace(name="Stream Prior Knowledge WS")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    generator = FakeGenerator(_minimal_graph_json())
    events: list[str] = []
    async for event in stream_generate_trail_events(
        session=db_session,
        generator=generator,
        workspace_id=ws.id,
        topic="Math",
        goal="Learn basics",
        target_depth="understand",
        prior_knowledge="Some background in geometry.",
    ):
        events.append(event)

    assert "event: done" in "".join(events)
    stored = await db_session.scalar(select(Trail).where(Trail.workspace_id == ws.id))
    assert stored is not None
    assert stored.prior_knowledge == "Some background in geometry."


async def test_stores_trail_and_graph(db_session: AsyncSession):
    ws = Workspace(name="Test WS")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    generator = FakeGenerator(_minimal_graph_json())
    trail, nodes, edges = await generate_and_store_trail(
        session=db_session,
        generator=generator,
        workspace_id=ws.id,
        topic="Math",
        goal="Learn basics",
        target_depth="understand",
    )

    assert trail.id is not None
    assert trail.workspace_id == ws.id
    assert trail.topic == "Math"
    assert len(nodes) == 10
    assert len(edges) == 9
    assert not generator.repair_called
    assert generator.max_nodes_seen == 40


async def test_stores_larger_graph_when_max_nodes_allows_it(db_session: AsyncSession):
    ws = Workspace(name="Large Graph WS")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    generator = FakeGenerator(_graph_json(45))
    _, nodes, edges = await generate_and_store_trail(
        session=db_session,
        generator=generator,
        workspace_id=ws.id,
        topic="Math",
        goal="Learn broadly",
        target_depth="understand",
        max_nodes=60,
    )

    assert len(nodes) == 45
    assert len(edges) == 44
    assert generator.max_nodes_seen == 60


async def test_missing_workspace_raises_lookup_error(db_session: AsyncSession):
    generator = FakeGenerator(_minimal_graph_json())
    with pytest.raises(LookupError, match="not found"):
        await generate_and_store_trail(
            session=db_session,
            generator=generator,
            workspace_id=uuid.uuid4(),
            topic="Math",
            goal="Learn basics",
            target_depth="understand",
        )


async def test_repair_called_on_bad_json(db_session: AsyncSession):
    ws = Workspace(name="Test WS")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    generator = FakeGenerator(
        json_str="not json at all",
        repair_json_str=_minimal_graph_json(),
    )
    trail, nodes, edges = await generate_and_store_trail(
        session=db_session,
        generator=generator,
        workspace_id=ws.id,
        topic="Math",
        goal="Learn basics",
        target_depth="understand",
    )
    assert generator.repair_called
    assert trail.id is not None


async def test_generation_error_leaves_no_partial_rows(db_session: AsyncSession):
    ws = Workspace(name="Test WS")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    generator = FakeGenerator(json_str="bad", repair_json_str="also bad")
    with pytest.raises(GenerationError):
        await generate_and_store_trail(
            session=db_session,
            generator=generator,
            workspace_id=ws.id,
            topic="Math",
            goal="Learn",
            target_depth="remember",
        )

    # No trail rows written (session was rolled back / never committed)
    from sqlalchemy import func, select

    result = await db_session.execute(select(func.count()).select_from(Trail))
    assert result.scalar() == 0


async def test_generate_raises_wraps_generation_error(db_session: AsyncSession):
    ws = Workspace(name="Test WS")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    generator = FakeGenerator(_minimal_graph_json(), raise_on_generate=True)
    with pytest.raises(GenerationError, match="LLM call failed"):
        await generate_and_store_trail(
            session=db_session,
            generator=generator,
            workspace_id=ws.id,
            topic="Math",
            goal="Learn basics",
            target_depth="understand",
        )


async def test_stream_emits_progress_delta_and_done(db_session: AsyncSession):
    ws = Workspace(name="Stream WS")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    generator = FakeGenerator(_minimal_graph_json())
    events: list[str] = []
    async for event in stream_generate_trail_events(
        session=db_session,
        generator=generator,
        workspace_id=ws.id,
        topic="Math",
        goal="Learn basics",
        target_depth="understand",
    ):
        events.append(event)

    body = "".join(events)
    assert "event: progress" in body
    assert "event: delta" in body
    assert "event: done" in body
    assert '"node_count":10' in body
    assert generator.max_nodes_seen == 40


async def test_stream_uses_reasoning_output_when_completion_is_empty(db_session: AsyncSession):
    ws = Workspace(name="Reasoning Stream WS")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    generator = ReasoningOnlyGenerator(_minimal_graph_json())
    events: list[str] = []
    async for event in stream_generate_trail_events(
        session=db_session,
        generator=generator,
        workspace_id=ws.id,
        topic="Math",
        goal="Learn basics",
        target_depth="understand",
    ):
        events.append(event)

    body = "".join(events)
    assert "event: thinking" in body
    assert "No completion text received" in body
    assert "event: done" in body
    assert '"node_count":10' in body


async def test_stream_llm_error_emits_error_event(db_session: AsyncSession):
    ws = Workspace(name="Stream Error WS")
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)

    generator = FakeGenerator(_minimal_graph_json(), raise_on_generate=True)
    events: list[str] = []
    async for event in stream_generate_trail_events(
        session=db_session,
        generator=generator,
        workspace_id=ws.id,
        topic="Math",
        goal="Learn basics",
        target_depth="understand",
    ):
        events.append(event)

    body = "".join(events)
    assert "event: error" in body
    assert "llm_error" in body


async def test_stream_missing_workspace_emits_error_event(db_session: AsyncSession):
    import uuid

    generator = FakeGenerator(_minimal_graph_json())
    events: list[str] = []
    async for event in stream_generate_trail_events(
        session=db_session,
        generator=generator,
        workspace_id=uuid.uuid4(),
        topic="Math",
        goal="Learn basics",
        target_depth="understand",
    ):
        events.append(event)

    body = "".join(events)
    assert "event: error" in body
    assert "not_found" in body
