"""Flashcard ROUTE/API smoke tests (Phase 15c).

Mirrors test_artifact_builder.py / test_concepts_api.py endpoint style: a
file-backed SQLite ``db_engine``/``session_factory`` (the 0017 migration targets
Postgres), ``dependency_overrides`` for ``get_session`` plus the generator /
embedder seams so NO real LLM/network is touched, and httpx/ASGITransport.

Covers the 4 endpoints plus the streaming generation path:
- POST .../flashcards/generate -> 200 deck + cards (fake generator).
- POST .../flashcards/generate/stream -> SSE status + done and persisted deck.
- GET  .../flashcards          -> deck + cards with scheduling state.
- POST .../flashcards/{id}/review -> box increments on yes; resets + lapses++ on no.
- GET  .../flashcards/export?format=csv|json -> well-formed CSV / round-trip JSON.
"""

from __future__ import annotations

import csv
import io
import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.api.flashcards import (
    get_embedder,
    get_flashcard_generator,
    get_session_factory,
)
from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.base import Base
from backend.app.models.concept import ConceptNode
from backend.app.models.source import (
    ConceptSourceLink,
    SourceChunk,
    SourceRecord,
    SourceRevision,
)
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.flashcard import FlashcardGenerationOutput, GeneratedCard


def _parse_sse(body: str) -> list[dict]:
    events: list[dict] = []
    current: dict = {}
    for line in body.splitlines():
        if line.startswith("event:"):
            current["event"] = line[6:].strip()
        elif line.startswith("data:"):
            current["data"] = json.loads(line[5:].strip())
        elif not line and current:
            events.append(current.copy())
            current = {}
    if current:
        events.append(current)
    return events


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# Fakes (no LLM / no network)
# ---------------------------------------------------------------------------


class _FakeGenerator:
    """Scriptable generator returning a fixed set of grounded cards."""

    def __init__(self, output: FlashcardGenerationOutput) -> None:
        self._output = output

    async def generate(self, *, concept_title, primer, existing_fronts, snippets, max_cards):
        return self._output

    async def repair(self, raw, error):  # pragma: no cover - not exercised here
        return raw


class _DisabledEmbedder:
    """Embeddings disabled => dedup gate skipped."""

    async def embed(self, texts):
        return None


# ---------------------------------------------------------------------------
# DB fixtures + seeding
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'flashcards_api.db'}", echo=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


async def _seed(session) -> tuple[Workspace, Trail, ConceptNode, uuid.UUID]:
    workspace = Workspace(name="WS")
    session.add(workspace)
    await session.flush()
    trail = Trail(
        workspace_id=workspace.id,
        title="Trail",
        topic="Biology",
        goal="Understand photosynthesis",
        target_depth="understand",
    )
    session.add(trail)
    await session.flush()
    concept = ConceptNode(
        trail_id=trail.id,
        slug=f"concept-{uuid.uuid4().hex[:8]}",
        title="Photosynthesis",
        node_type="concept",
        concept_level="subtopic",
        difficulty="beginner",
        bloom_level="understand",
        mastery_check_labels=["explain_photosynthesis"],
        metadata_json={},
    )
    session.add(concept)
    await session.flush()

    source = SourceRecord(
        workspace_id=workspace.id,
        origin="manual",
        access="public",
        title="Photosynthesis notes",
    )
    session.add(source)
    await session.flush()
    body = "Photosynthesis converts light energy into chemical energy."
    revision = SourceRevision(
        workspace_id=workspace.id,
        source_id=source.id,
        revision_number=1,
        object_key=f"key-{uuid.uuid4().hex[:8]}",
        content_hash="hash",
        file_size_bytes=len(body),
        parser_name="markdown",
        parser_version="1",
        status="parsed",
        raw_text=body,
    )
    session.add(revision)
    await session.flush()
    session.add(
        SourceChunk(
            source_revision_id=revision.id,
            workspace_id=workspace.id,
            chunk_index=0,
            text=body,
            char_start=0,
            char_end=len(body),
            line_start=1,
            line_end=1,
        )
    )
    session.add(ConceptSourceLink(concept_id=concept.id, source_id=source.id, relation="primary"))
    await session.commit()
    return workspace, trail, concept, revision.id


def _override_session(session_factory):
    async def override_session():
        async with session_factory() as s:
            yield s

    return override_session


# ---------------------------------------------------------------------------
# generate + stream + get
# ---------------------------------------------------------------------------


async def test_generate_returns_deck_and_cards(db_engine, session_factory):
    async with session_factory() as seed_session:
        workspace, trail, concept, revision_id = await _seed(seed_session)

    generator = _FakeGenerator(
        FlashcardGenerationOutput(
            cards=[
                GeneratedCard(
                    front="What does photosynthesis convert?",
                    back="Light into chemical energy",
                    source_ref=str(revision_id),
                ),
                GeneratedCard(
                    front="What is the energy source?", back="Light", source_ref=str(revision_id)
                ),
            ],
            exhausted=False,
        )
    )

    app.dependency_overrides[get_session] = _override_session(session_factory)
    app.dependency_overrides[get_flashcard_generator] = lambda: generator
    app.dependency_overrides[get_embedder] = lambda: _DisabledEmbedder()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            base = (
                f"/api/workspaces/{workspace.id}/trails/{trail.id}/concepts/{concept.id}/flashcards"
            )
            resp = await client.post(f"{base}/generate", json={})
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["exhausted"] is False
            assert len(body["deck"]["cards"]) == 2
            assert body["deck"]["cards"][0]["box"] == 1
    finally:
        app.dependency_overrides.clear()


async def test_stream_generate_emits_status_and_done_and_persists(db_engine, session_factory):
    async with session_factory() as seed_session:
        workspace, trail, concept, revision_id = await _seed(seed_session)

    generator = _FakeGenerator(
        FlashcardGenerationOutput(
            cards=[GeneratedCard(front="Q", back="A", source_ref=str(revision_id))]
        )
    )

    app.dependency_overrides[get_session] = _override_session(session_factory)
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_flashcard_generator] = lambda: generator
    app.dependency_overrides[get_embedder] = lambda: _DisabledEmbedder()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            base = (
                f"/api/workspaces/{workspace.id}/trails/{trail.id}/concepts/{concept.id}/flashcards"
            )
            resp = await client.post(f"{base}/generate/stream", json={})
            assert resp.status_code == 200, resp.text
            events = _parse_sse(resp.text)
            assert [event["data"]["type"] for event in events] == ["status", "done"]
            assert events[0]["data"]["status"] == "generating"
            assert events[1]["data"]["deck"]["cards"][0]["front"] == "Q"

            persisted = await client.get(base)
            assert persisted.status_code == 200, persisted.text
            assert persisted.json()["cards"][0]["front"] == "Q"
    finally:
        app.dependency_overrides.clear()


async def test_get_returns_deck_with_scheduling_state(db_engine, session_factory):
    async with session_factory() as seed_session:
        workspace, trail, concept, revision_id = await _seed(seed_session)

    generator = _FakeGenerator(
        FlashcardGenerationOutput(
            cards=[GeneratedCard(front="Q", back="A", source_ref=str(revision_id))]
        )
    )

    app.dependency_overrides[get_session] = _override_session(session_factory)
    app.dependency_overrides[get_flashcard_generator] = lambda: generator
    app.dependency_overrides[get_embedder] = lambda: _DisabledEmbedder()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            base = (
                f"/api/workspaces/{workspace.id}/trails/{trail.id}/concepts/{concept.id}/flashcards"
            )
            await client.post(f"{base}/generate", json={})

            resp = await client.get(base)
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert len(body["cards"]) == 1
            card = body["cards"][0]
            assert card["box"] == 1
            assert card["reps"] == 0
            assert card["lapses"] == 0
            assert card["due"] is None
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# review
# ---------------------------------------------------------------------------


async def test_review_yes_increments_box_then_no_resets_and_lapses(db_engine, session_factory):
    async with session_factory() as seed_session:
        workspace, trail, concept, revision_id = await _seed(seed_session)

    generator = _FakeGenerator(
        FlashcardGenerationOutput(
            cards=[GeneratedCard(front="Q", back="A", source_ref=str(revision_id))]
        )
    )

    app.dependency_overrides[get_session] = _override_session(session_factory)
    app.dependency_overrides[get_flashcard_generator] = lambda: generator
    app.dependency_overrides[get_embedder] = lambda: _DisabledEmbedder()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            base = (
                f"/api/workspaces/{workspace.id}/trails/{trail.id}/concepts/{concept.id}/flashcards"
            )
            gen = await client.post(f"{base}/generate", json={})
            card_id = gen.json()["deck"]["cards"][0]["id"]

            yes = await client.post(f"{base}/{card_id}/review", json={"recalled": True})
            assert yes.status_code == 200, yes.text
            assert yes.json()["box"] == 2
            assert yes.json()["reps"] == 1
            assert yes.json()["due"] is not None

            no = await client.post(f"{base}/{card_id}/review", json={"recalled": False})
            assert no.status_code == 200, no.text
            assert no.json()["box"] == 1
            assert no.json()["lapses"] == 1
            assert no.json()["reps"] == 2
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------


async def test_export_csv_is_well_formed(db_engine, session_factory):
    async with session_factory() as seed_session:
        workspace, trail, concept, revision_id = await _seed(seed_session)

    generator = _FakeGenerator(
        FlashcardGenerationOutput(
            cards=[
                GeneratedCard(
                    front="Front, with comma",
                    back="Back",
                    hint="hint",
                    source_ref=str(revision_id),
                )
            ]
        )
    )

    app.dependency_overrides[get_session] = _override_session(session_factory)
    app.dependency_overrides[get_flashcard_generator] = lambda: generator
    app.dependency_overrides[get_embedder] = lambda: _DisabledEmbedder()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            base = (
                f"/api/workspaces/{workspace.id}/trails/{trail.id}/concepts/{concept.id}/flashcards"
            )
            await client.post(f"{base}/generate", json={})

            resp = await client.get(f"{base}/export", params={"format": "csv"})
            assert resp.status_code == 200, resp.text
            assert resp.headers["content-type"].startswith("text/csv")
            text = resp.text
            assert text.startswith("#separator:Comma")
            assert "#columns:front,back,hint,source_ref,card_type" in text

            data_lines = [line for line in text.splitlines() if not line.startswith("#")]
            rows = list(csv.reader(io.StringIO("\n".join(data_lines))))
            assert len(rows) == 1
            assert rows[0][0] == "Front, with comma"
            assert rows[0][1] == "Back"
            assert rows[0][4] == "basic"
    finally:
        app.dependency_overrides.clear()


async def test_export_json_round_trips(db_engine, session_factory):
    async with session_factory() as seed_session:
        workspace, trail, concept, revision_id = await _seed(seed_session)

    generator = _FakeGenerator(
        FlashcardGenerationOutput(
            cards=[GeneratedCard(front="Q", back="A", source_ref=str(revision_id))]
        )
    )

    app.dependency_overrides[get_session] = _override_session(session_factory)
    app.dependency_overrides[get_flashcard_generator] = lambda: generator
    app.dependency_overrides[get_embedder] = lambda: _DisabledEmbedder()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            base = (
                f"/api/workspaces/{workspace.id}/trails/{trail.id}/concepts/{concept.id}/flashcards"
            )
            await client.post(f"{base}/generate", json={})

            resp = await client.get(f"{base}/export", params={"format": "json"})
            assert resp.status_code == 200, resp.text
            assert resp.headers["content-type"].startswith("application/json")
            exported = json.loads(resp.text)
            assert json.loads(json.dumps(exported)) == exported
            assert exported["cards"][0]["front"] == "Q"
            assert exported["cards"][0]["box"] == 1
    finally:
        app.dependency_overrides.clear()
