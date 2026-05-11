"""Service-level tests for trail_generation.py (no HTTP, no real LLM)."""

import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.app.models.base import Base
from backend.app.models.concept import ConceptEdge, ConceptNode  # noqa: F401
from backend.app.models.source import ConceptSourceLink, SourceRecord  # noqa: F401
from backend.app.models.trail import Trail  # noqa: F401
from backend.app.models.workspace import Workspace
from backend.app.services.trail_generation import GenerationError, generate_and_store_trail


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


def _minimal_graph_json(topic: str = "Math") -> str:
    return json.dumps(
        {
            "nodes": [
                {
                    "slug": "math-root",
                    "title": topic,
                    "node_type": "concept",
                    "concept_level": "umbrella",
                    "difficulty": "beginner",
                    "bloom_level": "understand",
                    "mastery_check_labels": [],
                    "metadata_json": {},
                },
                {
                    "slug": "addition",
                    "title": "Addition",
                    "node_type": "concept",
                    "concept_level": "topic",
                    "difficulty": "beginner",
                    "bloom_level": "remember",
                    "mastery_check_labels": [],
                    "metadata_json": {},
                },
                {
                    "slug": "subtraction",
                    "title": "Subtraction",
                    "node_type": "concept",
                    "concept_level": "topic",
                    "difficulty": "beginner",
                    "bloom_level": "remember",
                    "mastery_check_labels": [],
                    "metadata_json": {},
                },
            ],
            "edges": [
                {"source_slug": "math-root", "target_slug": "addition", "relation_type": "contains"},  # noqa: E501
                {"source_slug": "math-root", "target_slug": "subtraction", "relation_type": "contains"},  # noqa: E501
            ],
        }
    )


class FakeGenerator:
    def __init__(self, json_str: str, repair_json_str: str | None = None):
        self._json = json_str
        self._repair = repair_json_str
        self.repair_called = False

    async def generate(self, topic: str, goal: str, target_depth: str) -> str:
        return self._json

    async def repair(self, raw_json: str, error: str) -> str:
        self.repair_called = True
        if self._repair is not None:
            return self._repair
        return self._json


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
    assert len(nodes) == 3
    assert len(edges) == 2
    assert not generator.repair_called


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
