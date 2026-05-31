"""Flashcards subsystem tests (Phase 15c).

Mirrors test_pins.py / test_quizzes_service.py / test_artifact_builder.py style:
in-memory SQLite via ``Base.metadata.create_all`` (the 0017 migration targets
Postgres), fake generator + fake embedder, no LLM/network.

Covers:
- Leitner scheduler: yes promotes the box; no resets to box 1 and increments
  lapses; geometric intervals per box.
- Generator declines with ``exhausted: true`` instead of padding.
- Source-grounding: cards cite real refs; ungrounded cards are dropped; the
  no-source case is handled gracefully without calling the model.
- The embedding-similarity gate drops paraphrase duplicates.
- CSV export is well-formed Anki CSV and JSON round-trips.
- One-repair-then-fail on malformed generator output.
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.models.base import Base
from backend.app.models.concept import ConceptNode
from backend.app.models.flashcard import Flashcard
from backend.app.models.source import (
    ConceptSourceLink,
    SourceChunk,
    SourceRecord,
    SourceRevision,
)
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.flashcard import FlashcardGenerationOutput, GeneratedCard
from backend.app.services.flashcard_export import export_deck_csv, export_deck_json
from backend.app.services.flashcard_scheduler import (
    LEITNER_INTERVALS,
    MAX_BOX,
    interval_for_box,
    review,
)
from backend.app.services.flashcards import (
    FlashcardGenerationError,
    FlashcardGenerationManager,
    _parse_or_repair,
    generate_deck,
    get_deck,
    review_card,
    stream_generate_deck,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeGenerator:
    """Scriptable flashcard generator. No LLM/network."""

    def __init__(self, output: FlashcardGenerationOutput) -> None:
        self._output = output
        self.calls = 0

    async def generate(self, *, concept_title, primer, existing_fronts, snippets, max_cards):
        self.calls += 1
        return self._output

    async def repair(self, raw, error):  # pragma: no cover - not exercised here
        return raw


class _RepairGenerator:
    """Only exposes ``repair`` to exercise the one-repair-then-fail path."""

    def __init__(self, repair_output: str) -> None:
        self._repair_output = repair_output
        self.repair_calls = 0

    async def repair(self, raw, error):
        self.repair_calls += 1
        return self._repair_output


class _DisabledEmbedder:
    """Embeddings disabled => dedup gate is skipped (returns None)."""

    async def embed(self, texts):
        return None


class _KeywordEmbedder:
    """Deterministic fake: text -> a fixed one-hot vector by keyword group.

    Two paraphrases that share the keyword collide (cosine 1.0); a distinct card
    maps to a different axis.
    """

    async def embed(self, texts):
        vectors = []
        for text in texts:
            lowered = text.lower()
            if "light" in lowered:
                vectors.append([1.0, 0.0, 0.0])
            elif "chloroplast" in lowered:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors


class _FailingEmbedder:
    """Embedding backend unavailable => dedup gate falls back to pass-through."""

    async def embed(self, texts):
        raise ValueError("embedding backend unavailable")


class _BlockingGenerator:
    """Generator that can pause so stream subscribers can overlap or disconnect."""

    def __init__(self, output: FlashcardGenerationOutput) -> None:
        self._output = output
        self.calls = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def generate(self, *, concept_title, primer, existing_fronts, snippets, max_cards):
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return self._output

    async def repair(self, raw, error):  # pragma: no cover - not exercised here
        return raw


# ---------------------------------------------------------------------------
# DB fixtures + seeding
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'flashcards.db'}", echo=False)
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


async def _seed_concept(session) -> tuple[Workspace, Trail, ConceptNode]:
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
    return workspace, trail, concept


async def _seed_source(
    session, *, workspace: Workspace, concept: ConceptNode, body: str
) -> uuid.UUID:
    """Attach a parsed source + one chunk to the concept. Returns its revision id."""
    source = SourceRecord(
        workspace_id=workspace.id,
        origin="manual",
        access="public",
        title="Photosynthesis notes",
    )
    session.add(source)
    await session.flush()
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
    chunk = SourceChunk(
        source_revision_id=revision.id,
        workspace_id=workspace.id,
        chunk_index=0,
        text=body,
        char_start=0,
        char_end=len(body),
        line_start=1,
        line_end=1,
    )
    session.add(chunk)
    session.add(ConceptSourceLink(concept_id=concept.id, source_id=source.id, relation="primary"))
    await session.commit()
    return revision.id


# ---------------------------------------------------------------------------
# Scheduler (pure)
# ---------------------------------------------------------------------------


def test_yes_promotes_box_and_increments_reps():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    state = review(box=2, reps=3, lapses=1, recalled=True, now=now)
    assert state.box == 3
    assert state.reps == 4
    assert state.lapses == 1
    assert state.interval_days == interval_for_box(3)
    assert state.last_reviewed == now
    assert state.due == now.replace(day=1 + interval_for_box(3))


def test_yes_caps_at_max_box():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    state = review(box=MAX_BOX, reps=10, lapses=0, recalled=True, now=now)
    assert state.box == MAX_BOX
    assert state.interval_days == LEITNER_INTERVALS[-1]


def test_no_resets_to_box_one_and_increments_lapses():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    state = review(box=4, reps=5, lapses=2, recalled=False, now=now)
    assert state.box == 1
    assert state.lapses == 3
    assert state.reps == 6
    assert state.interval_days == LEITNER_INTERVALS[0]


def test_geometric_intervals_per_box():
    assert LEITNER_INTERVALS == (1, 3, 7, 16, 35)
    assert [interval_for_box(b) for b in range(1, MAX_BOX + 1)] == [1, 3, 7, 16, 35]
    # Clamped outside range.
    assert interval_for_box(0) == 1
    assert interval_for_box(99) == 35


# ---------------------------------------------------------------------------
# Generation: grounding, exhausted, dedup
# ---------------------------------------------------------------------------


async def test_no_source_declines_without_calling_model(session):
    workspace, trail, concept = await _seed_concept(session)
    generator = _FakeGenerator(
        FlashcardGenerationOutput(cards=[GeneratedCard(front="x", back="y")])
    )

    deck, exhausted, reason = await generate_deck(
        session,
        generator,
        _DisabledEmbedder(),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )

    assert generator.calls == 0  # never invents without sources
    assert exhausted is True
    assert "source" in reason.lower()
    assert deck.cards == []


async def test_generator_can_decline_with_exhausted(session):
    workspace, trail, concept = await _seed_concept(session)
    await _seed_source(session, workspace=workspace, concept=concept, body="Light reactions.")
    generator = _FakeGenerator(
        FlashcardGenerationOutput(cards=[], exhausted=True, reason="No more useful facts.")
    )

    deck, exhausted, reason = await generate_deck(
        session,
        generator,
        _DisabledEmbedder(),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )
    assert exhausted is True
    assert reason == "No more useful facts."
    assert deck.cards == []


async def test_generation_is_source_grounded_and_drops_invented_refs(session):
    workspace, trail, concept = await _seed_concept(session)
    revision_id = await _seed_source(
        session, workspace=workspace, concept=concept, body="Chlorophyll absorbs light."
    )
    generator = _FakeGenerator(
        FlashcardGenerationOutput(
            cards=[
                GeneratedCard(
                    front="What pigment absorbs light?",
                    back="Chlorophyll",
                    source_ref=str(revision_id),
                ),
                GeneratedCard(
                    front="Invented fact?",
                    back="Made up",
                    source_ref="not-a-real-revision",
                ),
            ]
        )
    )

    deck, _exhausted, _reason = await generate_deck(
        session,
        generator,
        _DisabledEmbedder(),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )

    assert [c.front for c in deck.cards] == ["What pigment absorbs light?"]
    assert deck.cards[0].source_ref == str(revision_id)


async def test_paraphrase_duplicates_dropped_by_embedding_gate(session):
    workspace, trail, concept = await _seed_concept(session)
    revision_id = await _seed_source(
        session, workspace=workspace, concept=concept, body="Photosynthesis basics."
    )
    ref = str(revision_id)
    generator = _FakeGenerator(
        FlashcardGenerationOutput(
            cards=[
                GeneratedCard(
                    front="What converts light to energy?", back="Photosynthesis", source_ref=ref
                ),
                GeneratedCard(
                    front="Which process converts light energy?",
                    back="Photosynthesis",
                    source_ref=ref,
                ),
                GeneratedCard(
                    front="Where does photosynthesis occur?", back="Chloroplast", source_ref=ref
                ),
            ]
        )
    )

    deck, _exhausted, _reason = await generate_deck(
        session,
        generator,
        _KeywordEmbedder(),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )

    fronts = [c.front for c in deck.cards]
    assert "What converts light to energy?" in fronts
    assert "Where does photosynthesis occur?" in fronts
    assert "Which process converts light energy?" not in fronts  # paraphrase dropped
    assert len(deck.cards) == 2


async def test_generation_continues_when_embedding_dedup_backend_unavailable(session):
    workspace, trail, concept = await _seed_concept(session)
    revision_id = await _seed_source(
        session, workspace=workspace, concept=concept, body="Photosynthesis basics."
    )
    ref = str(revision_id)
    generator = _FakeGenerator(
        FlashcardGenerationOutput(
            cards=[
                GeneratedCard(
                    front="What converts light to energy?", back="Photosynthesis", source_ref=ref
                ),
                GeneratedCard(
                    front="Which process converts light energy?",
                    back="Photosynthesis",
                    source_ref=ref,
                ),
            ]
        )
    )

    deck, _exhausted, _reason = await generate_deck(
        session,
        generator,
        _FailingEmbedder(),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )

    # Dedup is best-effort: backend failures should not fail generation.
    assert sorted(c.front for c in deck.cards) == [
        "What converts light to energy?",
        "Which process converts light energy?",
    ]


async def test_idempotent_generate_returns_existing_deck(session):
    workspace, trail, concept = await _seed_concept(session)
    revision_id = await _seed_source(session, workspace=workspace, concept=concept, body="Facts.")
    generator = _FakeGenerator(
        FlashcardGenerationOutput(
            cards=[GeneratedCard(front="Q", back="A", source_ref=str(revision_id))]
        )
    )
    await generate_deck(
        session,
        generator,
        _DisabledEmbedder(),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )
    assert generator.calls == 1

    # Second call without force/extend must not re-generate.
    deck, _exhausted, _reason = await generate_deck(
        session,
        generator,
        _DisabledEmbedder(),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )
    assert generator.calls == 1
    assert len(deck.cards) == 1


async def test_stream_generation_persists_after_subscriber_stops_early(session_factory):
    async with session_factory() as session:
        workspace, trail, concept = await _seed_concept(session)
        revision_id = await _seed_source(
            session, workspace=workspace, concept=concept, body="Facts."
        )

    generator = _BlockingGenerator(
        FlashcardGenerationOutput(
            cards=[GeneratedCard(front="Q", back="A", source_ref=str(revision_id))]
        )
    )
    manager = FlashcardGenerationManager()

    async def consume_first_event() -> str:
        async with session_factory() as request_session:
            stream = stream_generate_deck(
                request_session,
                generator,
                _DisabledEmbedder(),
                workspace_id=workspace.id,
                trail_id=trail.id,
                concept_id=concept.id,
                session_factory=session_factory,
                manager=manager,
            )
            async for event in stream:
                return event
        raise AssertionError("stream produced no events")

    first_event = await asyncio.wait_for(consume_first_event(), timeout=1)
    assert '"type": "status"' in first_event
    await asyncio.wait_for(generator.started.wait(), timeout=1)
    generator.release.set()

    for _ in range(20):
        await asyncio.sleep(0.01)
        async with session_factory() as verify_session:
            try:
                deck = await get_deck(
                    verify_session,
                    workspace_id=workspace.id,
                    trail_id=trail.id,
                    concept_id=concept.id,
                )
            except LookupError:
                continue
        assert [card.front for card in deck.cards] == ["Q"]
        break
    else:  # pragma: no cover - defensive timeout path
        raise AssertionError("detached flashcard generation never persisted the deck")

    await manager.shutdown()


async def test_stream_generation_dedupes_concurrent_subscribers(session_factory):
    async with session_factory() as session:
        workspace, trail, concept = await _seed_concept(session)
        revision_id = await _seed_source(
            session, workspace=workspace, concept=concept, body="Facts."
        )

    generator = _BlockingGenerator(
        FlashcardGenerationOutput(
            cards=[GeneratedCard(front="Q", back="A", source_ref=str(revision_id))]
        )
    )
    manager = FlashcardGenerationManager()

    async def collect_all_events() -> list[str]:
        async with session_factory() as request_session:
            stream = stream_generate_deck(
                request_session,
                generator,
                _DisabledEmbedder(),
                workspace_id=workspace.id,
                trail_id=trail.id,
                concept_id=concept.id,
                session_factory=session_factory,
                manager=manager,
            )
            return [event async for event in stream]

    first_task = asyncio.create_task(collect_all_events())
    second_task = asyncio.create_task(collect_all_events())
    await asyncio.wait_for(generator.started.wait(), timeout=1)
    generator.release.set()
    first_events, second_events = await asyncio.gather(first_task, second_task)

    assert generator.calls == 1
    for events in (first_events, second_events):
        assert any('"type": "status"' in event for event in events)
        assert any('"type": "done"' in event for event in events)

    await manager.shutdown()


# ---------------------------------------------------------------------------
# Review (Leitner applied + persisted)
# ---------------------------------------------------------------------------


async def test_review_persists_box_change(session):
    workspace, trail, concept = await _seed_concept(session)
    revision_id = await _seed_source(session, workspace=workspace, concept=concept, body="Facts.")
    generator = _FakeGenerator(
        FlashcardGenerationOutput(
            cards=[GeneratedCard(front="Q", back="A", source_ref=str(revision_id))]
        )
    )
    deck, _exhausted, _reason = await generate_deck(
        session,
        generator,
        _DisabledEmbedder(),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )
    card_id = deck.cards[0].id

    updated = await review_card(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        card_id=card_id,
        recalled=True,
    )
    assert updated.box == 2
    assert updated.reps == 1
    assert updated.due is not None

    updated = await review_card(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        card_id=card_id,
        recalled=False,
    )
    assert updated.box == 1
    assert updated.lapses == 1
    assert updated.reps == 2

    stored = await session.get(Flashcard, card_id)
    assert stored.box == 1
    assert stored.lapses == 1


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


async def test_csv_export_is_well_formed_anki_csv(session):
    workspace, trail, concept = await _seed_concept(session)
    revision_id = await _seed_source(session, workspace=workspace, concept=concept, body="Facts.")
    generator = _FakeGenerator(
        FlashcardGenerationOutput(
            cards=[
                GeneratedCard(
                    front="Front, with comma",
                    back="Back",
                    hint="hint",
                    source_ref=str(revision_id),
                ),
            ]
        )
    )
    await generate_deck(
        session,
        generator,
        _DisabledEmbedder(),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )
    deck = await get_deck(
        session, workspace_id=workspace.id, trail_id=trail.id, concept_id=concept.id
    )

    text = export_deck_csv(deck)
    assert text.startswith("#separator:Comma")
    assert "#columns:front,back,hint,source_ref,card_type" in text

    data_lines = [line for line in text.splitlines() if not line.startswith("#")]
    rows = list(csv.reader(io.StringIO("\n".join(data_lines))))
    assert len(rows) == 1
    assert rows[0][0] == "Front, with comma"  # comma preserved via quoting
    assert rows[0][1] == "Back"
    assert rows[0][4] == "basic"


async def test_json_export_round_trips(session):
    workspace, trail, concept = await _seed_concept(session)
    revision_id = await _seed_source(session, workspace=workspace, concept=concept, body="Facts.")
    generator = _FakeGenerator(
        FlashcardGenerationOutput(
            cards=[GeneratedCard(front="Q", back="A", source_ref=str(revision_id))]
        )
    )
    await generate_deck(
        session,
        generator,
        _DisabledEmbedder(),
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )
    deck = await get_deck(
        session, workspace_id=workspace.id, trail_id=trail.id, concept_id=concept.id
    )

    exported = export_deck_json(deck)
    assert json.loads(json.dumps(exported)) == exported
    assert exported["cards"][0]["front"] == "Q"
    assert exported["cards"][0]["box"] == 1


# ---------------------------------------------------------------------------
# Repair contract
# ---------------------------------------------------------------------------


async def test_one_repair_then_fail_on_malformed_output():
    generator = _RepairGenerator(repair_output="still not json")
    with pytest.raises(FlashcardGenerationError):
        await _parse_or_repair(generator, "not json at all")
    assert generator.repair_calls == 1


async def test_valid_output_parses_without_repair():
    generator = _RepairGenerator(repair_output="unused")
    raw = json.dumps({"cards": [{"front": "Q", "back": "A"}], "exhausted": False, "reason": ""})
    output = await _parse_or_repair(generator, raw)
    assert generator.repair_calls == 0
    assert output.cards[0].front == "Q"
