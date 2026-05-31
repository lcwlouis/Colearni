"""Artifact-builder sub-agent + detached generation tests (Phase 15a).

Mirrors test_concept_primers_service.py and test_tool_loop.py. Uses fake
builders/stubs only — no live LLM calls and no network.

Covers:
- The bounded retrieval loop stays within ``tutor_tool_call_budget`` and the
  parser fails after EXACTLY one repair attempt.
- A citation whose source_revision_id was not retrieved is dropped.
- A valid build persists an artifact retrievable via the list/get endpoints.
- Detached generation completes + persists after the SSE subscriber cancels.
- Single-flight: two near-simultaneous builds for the same (target, kind) share
  one generation.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from typing import cast
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.agents.provider_tools import (
    NormalizedStreamEvent,
    NormalizedToolCall,
    NormalizedToolResult,
)
from backend.app.api.artifacts import get_artifact_builder, get_session_factory
from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.artifact import Artifact
from backend.app.models.base import Base
from backend.app.models.concept import ConceptNode
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.services.artifact_builder import (
    ArtifactGenerationError,
    ArtifactGenerationManager,
    build_artifact,
    stream_artifact,
)
from backend.app.services.artifacts import get_artifact
from backend.app.settings import settings

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeArtifactBuilder:
    """Scriptable builder. No LLM/network."""

    def __init__(
        self,
        *,
        tool_rounds: list[list[NormalizedToolCall]] | None = None,
        final: str = "",
        stream_payload: str | None = None,
        repair_output: str | None = None,
    ) -> None:
        # tool_rounds[i] = tool calls emitted on the i-th retrieval_stream call.
        self.tool_rounds = tool_rounds or []
        self.final = final
        self.stream_payload = stream_payload if stream_payload is not None else final
        self.repair_output = repair_output
        self.retrieval_calls = 0
        self.generate_calls = 0
        self.stream_calls = 0
        self.repair_calls = 0

    async def retrieval_stream(self, messages, *, tools):
        idx = self.retrieval_calls
        self.retrieval_calls += 1
        calls = self.tool_rounds[idx] if idx < len(self.tool_rounds) else []
        for tc in calls:
            yield NormalizedStreamEvent.tool_call_event(tc)
        yield NormalizedStreamEvent.done_event()

    async def generate(self, messages):
        self.generate_calls += 1
        return self.final

    async def generate_stream(self, messages):
        self.stream_calls += 1
        payload = self.stream_payload
        yield ("thinking", "Drafting the artifact...")
        mid = len(payload) // 2
        yield ("token", payload[:mid])
        yield ("token", payload[mid:])

    async def repair(self, raw, error):
        self.repair_calls += 1
        return self.repair_output if self.repair_output is not None else raw


class _GatedArtifactBuilder(_FakeArtifactBuilder):
    """Streams the first token, then blocks until ``release`` is set."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.first_token = asyncio.Event()
        self.release = asyncio.Event()

    async def generate_stream(self, messages):
        self.stream_calls += 1
        payload = self.stream_payload
        mid = len(payload) // 2
        yield ("token", payload[:mid])
        self.first_token.set()
        await self.release.wait()
        yield ("token", payload[mid:])


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------


def _worked_example_dict(**overrides) -> dict:
    payload = {
        "artifact_version": 1,
        "kind": "worked_example",
        "title": "Solving 2x = 4",
        "caption": None,
        "text_fallback": "Divide both sides by 2 to get x = 2.",
        "provenance": {"source_ids": [], "visibility": "local_only", "citations": []},
        "data": {
            "steps": [{"label": "Isolate x", "detail": "Divide both sides by 2"}],
            "final_answer": "x = 2",
        },
    }
    payload.update(overrides)
    return payload


def _worked_example_json(**overrides) -> str:
    return json.dumps(_worked_example_dict(**overrides))


def _search_call(query: str = "topic", call_id: str | None = None) -> NormalizedToolCall:
    return NormalizedToolCall(
        call_id=call_id or f"search:{query}",
        name="search_sources",
        arguments={"query": query},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db_engine(tmp_path):
    # File-backed SQLite so a detached background task can open its OWN connection
    # concurrently with the request session (production uses Postgres pools).
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'artifacts.db'}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def session(session_factory):
    async with session_factory() as session:
        yield session


async def _seed(session) -> tuple[Workspace, Trail, ConceptNode]:
    workspace = Workspace(name="WS")
    session.add(workspace)
    await session.flush()
    trail = Trail(
        workspace_id=workspace.id,
        title="Trail",
        topic="Algebra",
        goal="Solve linear equations",
        target_depth="apply",
    )
    session.add(trail)
    await session.flush()
    concept = ConceptNode(
        trail_id=trail.id,
        slug=f"concept-{uuid.uuid4().hex[:8]}",
        title="Linear equations",
        node_type="concept",
        concept_level="subtopic",
        difficulty="beginner",
        bloom_level="apply",
        mastery_check_labels=["solve_linear"],
        metadata_json={},
    )
    session.add(concept)
    await session.commit()
    return workspace, trail, concept


# ---------------------------------------------------------------------------
# Budget + repair
# ---------------------------------------------------------------------------


async def test_builder_stays_within_budget_and_fails_after_one_repair(session):
    workspace, trail, concept = await _seed(session)
    # Always emit a tool call so the loop would run forever if unbounded.
    builder = _FakeArtifactBuilder(
        tool_rounds=[[_search_call(f"q{i}")] for i in range(settings.tutor_tool_call_budget + 3)],
        final="not json at all",
        repair_output="still not json",
    )

    exec_count = 0

    async def fake_exec(tc, *, session, workspace_id, concept_id):
        nonlocal exec_count
        exec_count += 1
        return NormalizedToolResult(call_id=tc.call_id, name=tc.name, content="no revisions here")

    with patch(
        "backend.app.services.artifact_builder.execute_retrieval_tool",
        side_effect=fake_exec,
    ):
        with pytest.raises(ArtifactGenerationError):
            await build_artifact(
                session,
                builder,
                workspace_id=workspace.id,
                trail_id=trail.id,
                kind="worked_example",
                concept_id=concept.id,
            )

    # Exactly `budget` tool executions despite more rounds being offered.
    assert exec_count == settings.tutor_tool_call_budget
    # Exactly one repair attempt before failing.
    assert builder.repair_calls == 1


# ---------------------------------------------------------------------------
# Citation dropping
# ---------------------------------------------------------------------------


async def test_disallowed_citation_is_dropped(session):
    workspace, trail, concept = await _seed(session)
    kept = str(uuid.uuid4())
    dropped = str(uuid.uuid4())
    builder = _FakeArtifactBuilder(
        tool_rounds=[[_search_call("linear")]],
        final=_worked_example_json(
            provenance={
                "source_ids": [],
                "visibility": "source_derived",
                "citations": [
                    {"source_revision_id": kept, "quote": "keep"},
                    {"source_revision_id": dropped, "quote": "drop"},
                ],
            }
        ),
    )

    async def fake_exec(tc, *, session, workspace_id, concept_id):
        # Mimic the search_sources result formatter that prints the revision id.
        return NormalizedToolResult(
            call_id=tc.call_id,
            name=tc.name,
            content=f"Source: doc\nLines 1-2 | revision: {kept}\nsome text",
        )

    with patch(
        "backend.app.services.artifact_builder.execute_retrieval_tool",
        side_effect=fake_exec,
    ):
        artifact = await build_artifact(
            session,
            builder,
            workspace_id=workspace.id,
            trail_id=trail.id,
            kind="worked_example",
            concept_id=concept.id,
        )

    # Only the retrieved revision survives; the unseen citation is dropped.
    assert artifact.source_refs_json == [kept]
    # A citation remains, so source_derived is preserved.
    assert artifact.visibility == "source_derived"


async def test_no_citations_downgrades_to_local_only(session):
    workspace, trail, concept = await _seed(session)
    unseen = str(uuid.uuid4())
    builder = _FakeArtifactBuilder(
        tool_rounds=[],  # no retrieval => empty allow-set
        final=_worked_example_json(
            provenance={
                "source_ids": [],
                "visibility": "source_derived",
                "citations": [{"source_revision_id": unseen}],
            }
        ),
    )

    artifact = await build_artifact(
        session,
        builder,
        workspace_id=workspace.id,
        trail_id=trail.id,
        kind="worked_example",
        concept_id=concept.id,
    )

    # The only citation was dropped, so visibility is conservatively downgraded.
    assert artifact.source_refs_json == []
    assert artifact.visibility == "local_only"


# ---------------------------------------------------------------------------
# Valid build persists + retrievable via list/get endpoints
# ---------------------------------------------------------------------------


async def test_valid_build_persists_and_is_retrievable_via_endpoints(db_engine, session_factory):
    async with session_factory() as seed_session:
        workspace, trail, concept = await _seed(seed_session)

    builder = _FakeArtifactBuilder(tool_rounds=[], final=_worked_example_json())

    async def override_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_artifact_builder] = lambda: builder
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            base = f"/api/workspaces/{workspace.id}/trails/{trail.id}/artifacts"
            build = await client.post(
                f"{base}/build",
                json={"kind": "worked_example", "concept_id": str(concept.id)},
            )
            assert build.status_code == 200, build.text
            artifact_id = build.json()["id"]
            assert build.json()["artifact_type"] == "worked_example"

            listed = await client.get(base, params={"concept_id": str(concept.id)})
            assert listed.status_code == 200
            assert [a["id"] for a in listed.json()["artifacts"]] == [artifact_id]

            fetched = await client.get(f"{base}/{artifact_id}")
            assert fetched.status_code == 200
            assert fetched.json()["id"] == artifact_id
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Detached generation survives subscriber cancellation
# ---------------------------------------------------------------------------


async def test_detached_generation_persists_when_subscriber_cancels(session, session_factory):
    workspace, trail, concept = await _seed(session)
    # Capture primitive ids now: after the detached task drains, lazily loading
    # an expired ORM attribute on the parent session would fail (MissingGreenlet).
    workspace_id, trail_id, concept_id = workspace.id, trail.id, concept.id
    manager = ArtifactGenerationManager()
    builder = _GatedArtifactBuilder(tool_rounds=[], stream_payload=_worked_example_json())

    stream = cast(
        AsyncGenerator[str, None],
        stream_artifact(
            session,
            builder,
            workspace_id=workspace_id,
            trail_id=trail_id,
            kind="worked_example",
            concept_id=concept_id,
            session_factory=session_factory,
            manager=manager,
        ),
    )
    # Consume to the first preview token, then "disconnect" mid-flight.
    async for event in stream:
        if "event: token" in event:
            break
    await stream.aclose()

    # Let the detached generation finish; it owns its own session and persists.
    builder.release.set()
    await manager.drain()

    async with session_factory() as fresh:
        rows = (
            await fresh.execute(
                select(Artifact.id, Artifact.artifact_type).where(Artifact.trail_id == trail_id)
            )
        ).all()
    count = len(rows)
    first_type = rows[0][1] if rows else None
    assert count == 1
    assert first_type == "worked_example"
    # Exactly one model run despite the disconnect.
    assert builder.stream_calls == 1


# ---------------------------------------------------------------------------
# Single-flight: concurrent builds share one generation
# ---------------------------------------------------------------------------


async def test_concurrent_builds_share_single_generation(session, session_factory):
    workspace, trail, concept = await _seed(session)
    manager = ArtifactGenerationManager()
    builder = _GatedArtifactBuilder(tool_rounds=[], stream_payload=_worked_example_json())

    async def consume() -> str:
        return "".join(
            [
                event
                async for event in manager.stream(
                    builder,
                    session_factory,
                    workspace_id=workspace.id,
                    trail_id=trail.id,
                    concept_id=concept.id,
                    kind="worked_example",
                )
            ]
        )

    first = asyncio.create_task(consume())
    second = asyncio.create_task(consume())
    await asyncio.wait_for(builder.first_token.wait(), timeout=1)
    builder.release.set()

    body_first, body_second = await asyncio.gather(first, second)

    assert "event: done" in body_first
    assert "event: done" in body_second
    # Only ONE model run for the (target, kind).
    assert builder.stream_calls == 1

    async with session_factory() as fresh:
        rows = (await fresh.execute(select(Artifact.id).where(Artifact.trail_id == trail.id))).all()
        count = len(rows)
    # And only ONE artifact persisted.
    assert count == 1


async def test_get_artifact_round_trips_after_build(session):
    workspace, trail, concept = await _seed(session)
    builder = _FakeArtifactBuilder(tool_rounds=[], final=_worked_example_json())
    artifact = await build_artifact(
        session,
        builder,
        workspace_id=workspace.id,
        trail_id=trail.id,
        kind="worked_example",
        concept_id=concept.id,
    )
    fetched = await get_artifact(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        artifact_id=artifact.id,
    )
    assert fetched.id == artifact.id


async def test_second_build_dedupes_to_existing_without_model_call(db_engine, session_factory):
    """A non-force second build returns the existing artifact via the route
    (ArtifactRead.model_validate) without a second model call. Regression for the
    rollback-expiry (MissingGreenlet) bug on the dedupe-return path."""
    async with session_factory() as seed_session:
        workspace, trail, concept = await _seed(seed_session)
        workspace_id, trail_id, concept_id = workspace.id, trail.id, concept.id

    builder = _FakeArtifactBuilder(tool_rounds=[], final=_worked_example_json())

    async def override_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_artifact_builder] = lambda: builder
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            base = f"/api/workspaces/{workspace_id}/trails/{trail_id}/artifacts/build"
            body = {"kind": "worked_example", "concept_id": str(concept_id)}
            first = await client.post(base, json=body)
            assert first.status_code == 200
            second = await client.post(base, json=body)
            assert second.status_code == 200
            assert second.json()["id"] == first.json()["id"]
    finally:
        app.dependency_overrides.clear()

    # Only the first build invoked the model; the second deduped to the existing.
    assert builder.generate_calls == 1
