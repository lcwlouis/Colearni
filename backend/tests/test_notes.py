"""Notes feature tests.

Mirrors test_pins.py fixtures/style. Uses in-memory SQLite via
``Base.metadata.create_all`` (the 0019 migration targets Postgres only) and
exercises the notes service directly plus the thin routes.

Covers:
- Create/list/update/delete round-trip (service + routes).
- Newest-first ordering and optional concept filtering.
- Partial PATCH semantics (title-only, body-only, clear title).
- Workspace/trail ownership enforcement (cross-trail / cross-workspace 404).
- Concept must belong to the trail when provided.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.base import Base
from backend.app.models.concept import ConceptNode
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.note import NoteCreateRequest, NoteUpdateRequest
from backend.app.services.notes import (
    create_note,
    delete_note,
    list_notes,
    update_note,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'notes.db'}", echo=False)
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


async def _seed_trail(session, *, workspace: Workspace) -> tuple[Trail, ConceptNode]:
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
    await session.flush()
    return trail, concept


async def _seed(session) -> tuple[Workspace, Trail, ConceptNode]:
    workspace = Workspace(name="WS")
    session.add(workspace)
    await session.flush()
    trail, concept = await _seed_trail(session, workspace=workspace)
    await session.commit()
    return workspace, trail, concept


# ---------------------------------------------------------------------------
# Create / list
# ---------------------------------------------------------------------------


async def test_create_and_list_note(session):
    workspace, trail, _concept = await _seed(session)

    note = await create_note(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        payload=NoteCreateRequest(title="My note", body="Some **markdown** body"),
    )
    assert note.title == "My note"
    assert note.body == "Some **markdown** body"
    assert note.concept_id is None

    notes = await list_notes(session, workspace_id=workspace.id, trail_id=trail.id)
    assert [n.id for n in notes] == [note.id]


async def test_create_concept_scoped_note_and_filter(session):
    workspace, trail, concept = await _seed(session)

    trail_note = await create_note(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        payload=NoteCreateRequest(body="trail level"),
    )
    concept_note = await create_note(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        payload=NoteCreateRequest(body="concept level", concept_id=concept.id),
    )

    filtered = await list_notes(
        session, workspace_id=workspace.id, trail_id=trail.id, concept_id=concept.id
    )
    assert [n.id for n in filtered] == [concept_note.id]

    all_notes = await list_notes(session, workspace_id=workspace.id, trail_id=trail.id)
    assert {n.id for n in all_notes} == {trail_note.id, concept_note.id}


async def test_list_is_newest_first(session):
    workspace, trail, _concept = await _seed(session)

    older = await create_note(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        payload=NoteCreateRequest(body="older"),
    )
    newer = await create_note(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        payload=NoteCreateRequest(body="newer"),
    )
    # SQLite's func.now() has second resolution, so set distinct timestamps
    # explicitly to deterministically exercise the newest-first ordering.
    older.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    newer.created_at = datetime(2026, 1, 2, tzinfo=UTC)
    await session.commit()

    notes = await list_notes(session, workspace_id=workspace.id, trail_id=trail.id)
    assert [n.id for n in notes] == [newer.id, older.id]


async def test_create_note_rejects_concept_outside_trail(session):
    workspace, trail_a, _concept_a = await _seed(session)
    _trail_b, concept_b = await _seed_trail(session, workspace=workspace)
    await session.commit()

    with pytest.raises(LookupError):
        await create_note(
            session,
            workspace_id=workspace.id,
            trail_id=trail_a.id,
            payload=NoteCreateRequest(body="bad", concept_id=concept_b.id),
        )


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


async def test_update_body_only_preserves_title(session):
    workspace, trail, _concept = await _seed(session)
    note = await create_note(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        payload=NoteCreateRequest(title="Keep me", body="old"),
    )

    updated = await update_note(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        note_id=note.id,
        payload=NoteUpdateRequest(body="new body"),
    )
    assert updated.title == "Keep me"
    assert updated.body == "new body"


async def test_update_can_clear_title(session):
    workspace, trail, _concept = await _seed(session)
    note = await create_note(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        payload=NoteCreateRequest(title="Remove me", body="body"),
    )

    updated = await update_note(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        note_id=note.id,
        payload=NoteUpdateRequest(title=None),
    )
    assert updated.title is None
    assert updated.body == "body"


async def test_update_empty_payload_raises(session):
    workspace, trail, _concept = await _seed(session)
    note = await create_note(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        payload=NoteCreateRequest(body="body"),
    )

    with pytest.raises(ValueError):
        await update_note(
            session,
            workspace_id=workspace.id,
            trail_id=trail.id,
            note_id=note.id,
            payload=NoteUpdateRequest(),
        )


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


async def test_delete_note(session):
    workspace, trail, _concept = await _seed(session)
    note = await create_note(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        payload=NoteCreateRequest(body="body"),
    )

    await delete_note(session, workspace_id=workspace.id, trail_id=trail.id, note_id=note.id)
    notes = await list_notes(session, workspace_id=workspace.id, trail_id=trail.id)
    assert notes == []


# ---------------------------------------------------------------------------
# Ownership enforcement
# ---------------------------------------------------------------------------


async def test_cross_trail_note_access_rejected(session):
    workspace, trail_a, _concept_a = await _seed(session)
    trail_b, _concept_b = await _seed_trail(session, workspace=workspace)
    await session.commit()

    note = await create_note(
        session,
        workspace_id=workspace.id,
        trail_id=trail_a.id,
        payload=NoteCreateRequest(body="a"),
    )

    with pytest.raises(LookupError):
        await update_note(
            session,
            workspace_id=workspace.id,
            trail_id=trail_b.id,
            note_id=note.id,
            payload=NoteUpdateRequest(body="hacked"),
        )
    with pytest.raises(LookupError):
        await delete_note(session, workspace_id=workspace.id, trail_id=trail_b.id, note_id=note.id)


async def test_list_rejects_unknown_trail(session):
    workspace, _trail, _concept = await _seed(session)
    with pytest.raises(LookupError):
        await list_notes(session, workspace_id=workspace.id, trail_id=uuid.uuid4())


# ---------------------------------------------------------------------------
# Route smoke test
# ---------------------------------------------------------------------------


async def test_note_routes_round_trip(session_factory):
    async with session_factory() as seed_session:
        workspace, trail, concept = await _seed(seed_session)

    async def override_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            base = f"/api/workspaces/{workspace.id}/trails/{trail.id}/notes"

            created = await client.post(
                base, json={"title": "First", "body": "hello", "concept_id": str(concept.id)}
            )
            assert created.status_code == 200, created.text
            note_id = created.json()["id"]
            assert created.json()["concept_id"] == str(concept.id)

            listed = await client.get(base)
            assert listed.status_code == 200
            assert [n["id"] for n in listed.json()["notes"]] == [note_id]

            filtered = await client.get(base, params={"concept_id": str(concept.id)})
            assert [n["id"] for n in filtered.json()["notes"]] == [note_id]

            patched = await client.patch(f"{base}/{note_id}", json={"body": "updated"})
            assert patched.status_code == 200, patched.text
            assert patched.json()["body"] == "updated"
            assert patched.json()["title"] == "First"

            deleted = await client.delete(f"{base}/{note_id}")
            assert deleted.status_code == 200, deleted.text

            listed = await client.get(base)
            assert listed.json()["notes"] == []
    finally:
        app.dependency_overrides.clear()


async def test_note_route_create_unknown_trail_404(session_factory):
    async with session_factory() as seed_session:
        workspace, _trail, _concept = await _seed(seed_session)

    async def override_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/api/workspaces/{workspace.id}/trails/{uuid.uuid4()}/notes",
                json={"body": "hi"},
            )
            assert resp.status_code == 404, resp.text
            assert resp.json()["error"]["code"] == "not_found"
    finally:
        app.dependency_overrides.clear()
