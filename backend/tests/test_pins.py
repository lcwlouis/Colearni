"""Pin system tests (Phase 15b).

Mirrors test_artifact_builder.py fixtures/style. Uses in-memory SQLite via
``Base.metadata.create_all`` (the 0016 migration targets Postgres only) and
exercises the pin service directly plus the thin routes.

Covers:
- Pinning then unpinning an artifact AND a quiz attempt round-trips per-trail.
- Pin is idempotent (double-pin => one row).
- The Saved list aggregates BOTH item types scoped to the trail.
- Cross-trail / cross-workspace pins are rejected.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.artifact import Artifact
from backend.app.models.base import Base
from backend.app.models.concept import ConceptNode
from backend.app.models.flashcard import Flashcard, FlashcardDeck
from backend.app.models.mastery import QuizAttempt
from backend.app.models.pin import Pin
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.services.pins import list_pins, pin_item, unpin_item

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'pins.db'}", echo=False)
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


async def _make_artifact(
    session, *, workspace: Workspace, trail: Trail, concept: ConceptNode
) -> Artifact:
    artifact = Artifact(
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        artifact_type="worked_example",
        title="Worked example",
        payload_json={"kind": "worked_example", "title": "Worked example"},
        source_refs_json=[],
        visibility="local_only",
    )
    session.add(artifact)
    await session.flush()
    return artifact


async def _make_attempt(session, *, concept: ConceptNode) -> QuizAttempt:
    attempt = QuizAttempt(
        concept_id=concept.id,
        quiz_type="practice",
        questions_json=[
            {
                "id": "q1",
                "type": "short_answer",
                "prompt": "What is x?",
                "mastery_label": "solve_linear",
                "difficulty": "standard",
            }
        ],
        answers_json=[{"question_id": "q1", "answer": "42"}],
        evaluator_feedback="Good",
        passed=True,
        score=0.9,
    )
    session.add(attempt)
    await session.flush()
    return attempt


async def _make_deck(
    session, *, workspace: Workspace, trail: Trail, concept: ConceptNode
) -> FlashcardDeck:
    deck = FlashcardDeck(
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        title="Photosynthesis deck",
    )
    session.add(deck)
    await session.flush()
    session.add(
        Flashcard(
            deck_id=deck.id,
            workspace_id=workspace.id,
            front="Q",
            back="A",
            source_ref="ref",
            card_type="basic",
        )
    )
    await session.flush()
    return deck


async def _seed(session) -> tuple[Workspace, Trail, ConceptNode, Artifact, QuizAttempt]:
    workspace = Workspace(name="WS")
    session.add(workspace)
    await session.flush()
    trail, concept = await _seed_trail(session, workspace=workspace)
    artifact = await _make_artifact(session, workspace=workspace, trail=trail, concept=concept)
    attempt = await _make_attempt(session, concept=concept)
    await session.commit()
    return workspace, trail, concept, artifact, attempt


# ---------------------------------------------------------------------------
# Round-trip + idempotency
# ---------------------------------------------------------------------------


async def test_pin_unpin_artifact_round_trips(session):
    workspace, trail, _concept, artifact, _attempt = await _seed(session)

    await pin_item(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        item_type="artifact",
        item_id=artifact.id,
    )
    pins = await list_pins(session, workspace_id=workspace.id, trail_id=trail.id)
    assert [a.id for a in pins.artifacts] == [artifact.id]

    await unpin_item(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        item_type="artifact",
        item_id=artifact.id,
    )
    pins = await list_pins(session, workspace_id=workspace.id, trail_id=trail.id)
    assert pins.artifacts == []


async def test_pin_unpin_quiz_attempt_round_trips(session):
    workspace, trail, _concept, _artifact, attempt = await _seed(session)

    await pin_item(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        item_type="quiz_attempt",
        item_id=attempt.id,
    )
    pins = await list_pins(session, workspace_id=workspace.id, trail_id=trail.id)
    assert [a.id for a in pins.quiz_attempts] == [attempt.id]

    await unpin_item(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        item_type="quiz_attempt",
        item_id=attempt.id,
    )
    pins = await list_pins(session, workspace_id=workspace.id, trail_id=trail.id)
    assert pins.quiz_attempts == []


async def test_pin_is_idempotent(session):
    workspace, trail, _concept, artifact, _attempt = await _seed(session)

    for _ in range(3):
        await pin_item(
            session,
            workspace_id=workspace.id,
            trail_id=trail.id,
            item_type="artifact",
            item_id=artifact.id,
        )

    count = await session.scalar(select(func.count()).select_from(Pin))
    assert count == 1


async def test_unpin_absent_is_noop(session):
    workspace, trail, _concept, artifact, _attempt = await _seed(session)
    # Never pinned; unpin must not raise.
    await unpin_item(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        item_type="artifact",
        item_id=artifact.id,
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


async def test_list_aggregates_both_item_types_scoped_to_trail(session):
    workspace, trail, _concept, artifact, attempt = await _seed(session)

    await pin_item(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        item_type="artifact",
        item_id=artifact.id,
    )
    await pin_item(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        item_type="quiz_attempt",
        item_id=attempt.id,
    )

    pins = await list_pins(session, workspace_id=workspace.id, trail_id=trail.id)
    assert [a.id for a in pins.artifacts] == [artifact.id]
    assert [a.id for a in pins.quiz_attempts] == [attempt.id]


# ---------------------------------------------------------------------------
# Cross-trail / cross-workspace rejection
# ---------------------------------------------------------------------------


async def test_pin_unpin_flashcard_deck_round_trips(session):
    workspace, trail, concept, _artifact, _attempt = await _seed(session)
    deck = await _make_deck(session, workspace=workspace, trail=trail, concept=concept)
    await session.commit()

    await pin_item(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        item_type="flashcard",
        item_id=deck.id,
    )
    pins = await list_pins(session, workspace_id=workspace.id, trail_id=trail.id)
    assert [d.id for d in pins.flashcards] == [deck.id]
    assert [c.front for c in pins.flashcards[0].cards] == ["Q"]

    await unpin_item(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        item_type="flashcard",
        item_id=deck.id,
    )
    pins = await list_pins(session, workspace_id=workspace.id, trail_id=trail.id)
    assert pins.flashcards == []


async def test_cross_trail_flashcard_pin_rejected(session):
    workspace, trail_a, concept, _artifact, _attempt = await _seed(session)
    deck = await _make_deck(session, workspace=workspace, trail=trail_a, concept=concept)
    trail_b, _concept_b = await _seed_trail(session, workspace=workspace)
    await session.commit()

    with pytest.raises(LookupError):
        await pin_item(
            session,
            workspace_id=workspace.id,
            trail_id=trail_b.id,
            item_type="flashcard",
            item_id=deck.id,
        )


async def test_cross_trail_artifact_pin_rejected(session):
    workspace, trail_a, _concept, artifact, _attempt = await _seed(session)
    trail_b, _concept_b = await _seed_trail(session, workspace=workspace)
    await session.commit()

    with pytest.raises(LookupError):
        await pin_item(
            session,
            workspace_id=workspace.id,
            trail_id=trail_b.id,
            item_type="artifact",
            item_id=artifact.id,
        )


async def test_cross_workspace_attempt_pin_rejected(session):
    workspace, trail, _concept, _artifact, attempt = await _seed(session)
    other_ws = Workspace(name="Other")
    session.add(other_ws)
    await session.flush()
    other_trail, _other_concept = await _seed_trail(session, workspace=other_ws)
    await session.commit()

    with pytest.raises(LookupError):
        await pin_item(
            session,
            workspace_id=other_ws.id,
            trail_id=other_trail.id,
            item_type="quiz_attempt",
            item_id=attempt.id,
        )


# ---------------------------------------------------------------------------
# Route smoke test
# ---------------------------------------------------------------------------


async def test_pin_routes_round_trip(session_factory):
    async with session_factory() as seed_session:
        workspace, trail, _concept, artifact, attempt = await _seed(seed_session)

    async def override_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            base = f"/api/workspaces/{workspace.id}/trails/{trail.id}/pins"

            resp = await client.post(
                base, json={"item_type": "artifact", "item_id": str(artifact.id)}
            )
            assert resp.status_code == 200, resp.text
            resp = await client.post(
                base, json={"item_type": "quiz_attempt", "item_id": str(attempt.id)}
            )
            assert resp.status_code == 200, resp.text

            listed = await client.get(base)
            assert listed.status_code == 200
            body = listed.json()
            assert [a["id"] for a in body["artifacts"]] == [str(artifact.id)]
            assert [a["id"] for a in body["quiz_attempts"]] == [str(attempt.id)]

            unp = await client.delete(
                base, params={"item_type": "artifact", "item_id": str(artifact.id)}
            )
            assert unp.status_code == 200, unp.text

            listed = await client.get(base)
            assert listed.json()["artifacts"] == []
            assert [a["id"] for a in listed.json()["quiz_attempts"]] == [str(attempt.id)]
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Concept pin tests
# ---------------------------------------------------------------------------


async def test_pin_concept_roundtrip(session):
    workspace, trail, concept, _artifact, _attempt = await _seed(session)

    await pin_item(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        item_type="concept",
        item_id=concept.id,
    )
    pins = await list_pins(session, workspace_id=workspace.id, trail_id=trail.id)
    assert len(pins.concepts) == 1
    assert pins.concepts[0].concept_id == concept.id
    assert pins.concepts[0].concept_title == concept.title
    assert pins.concepts[0].trail_id == trail.id


async def test_unpin_concept(session):
    workspace, trail, concept, _artifact, _attempt = await _seed(session)

    await pin_item(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        item_type="concept",
        item_id=concept.id,
    )
    await unpin_item(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        item_type="concept",
        item_id=concept.id,
    )
    pins = await list_pins(session, workspace_id=workspace.id, trail_id=trail.id)
    assert pins.concepts == []

