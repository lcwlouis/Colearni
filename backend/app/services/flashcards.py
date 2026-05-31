"""Flashcard generation + review service (dedicated subsystem, Phase 15c).

The canonical store is relational (``flashcard_decks`` + ``flashcards``); CSV/JSON
are export only. Generation is SOURCE-GROUNDED, ATOMIC and DEDUP-AWARE:

- Grounding context is the concept's linked source chunks (real
  ``source_revision_id``s) plus its cached primer (orientation only). With NO
  linked sources the generator is never called — the deck stays empty and the
  service reports ``exhausted`` rather than letting the model invent facts.
- The generator returns ``{cards, exhausted, reason}`` so it can decline instead
  of padding garbage. Output is strict JSON + EXACTLY ONE repair attempt.
- Cards whose ``source_ref`` is not one of the provided grounding refs are
  dropped (no invented citations).
- A deterministic embedding-similarity gate drops paraphrase-duplicates against
  existing cards and within the new batch (cosine over the embedding client).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import uuid
from datetime import UTC, datetime
from hashlib import blake2b
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from openai import OpenAIError
from sqlalchemy import delete, select, text

from backend.app.agents.prompts import prompt_registry
from backend.app.models.flashcard import Flashcard, FlashcardDeck
from backend.app.models.source import ConceptSourceLink, SourceChunk, SourceRecord, SourceRevision
from backend.app.schemas.flashcard import (
    FlashcardDeckRead,
    FlashcardGenerationOutput,
    FlashcardRead,
    GeneratedCard,
)
from backend.app.services.concept_primers import read_cached_primer
from backend.app.services.conversations import validate_concept_scope
from backend.app.services.flashcard_scheduler import review as schedule_review

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from backend.app.agents.llm_client import LLMClient
    from backend.app.agents.prompts.registry import PromptRegistry
    from backend.app.models.concept import ConceptNode

# Generation caps: keep cards/concept bounded and the deck soft-capped.
MAX_CARDS_PER_GENERATION = 8
DECK_SOFT_CAP = 30
# Grounding retrieval bounds.
GROUNDING_CHUNK_LIMIT = 12
_SNIPPET_CHARS = 600
# Cosine threshold above which two card texts are treated as paraphrase-duplicates.
DEDUP_THRESHOLD = 0.92
_GENERATION_MAX_TOKENS = 1400

logger = logging.getLogger(__name__)

_FlashcardJobKey = tuple[uuid.UUID, uuid.UUID, uuid.UUID, bool, bool]


class FlashcardGenerationError(Exception):
    pass


# ---------------------------------------------------------------------------
# Injectable collaborators (tests substitute fakes; no LLM/network/embeddings).
# ---------------------------------------------------------------------------


@runtime_checkable
class FlashcardGenerator(Protocol):
    async def generate(
        self,
        *,
        concept_title: str,
        primer: str,
        existing_fronts: list[str],
        snippets: str,
        max_cards: int,
    ) -> FlashcardGenerationOutput: ...

    async def repair(self, raw: str, error: str) -> str:
        # Optional: return corrected generator JSON for a validation failure.
        ...


@runtime_checkable
class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]] | None: ...


class LLMFlashcardGenerator:
    """Production generator: structured JSON + exactly one repair attempt."""

    def __init__(self, client: LLMClient, registry: PromptRegistry = prompt_registry) -> None:
        self._client = client
        self._registry = registry

    async def generate(
        self,
        *,
        concept_title: str,
        primer: str,
        existing_fronts: list[str],
        snippets: str,
        max_cards: int,
    ) -> FlashcardGenerationOutput:
        prompt = self._registry.render(
            "flashcard_generation",
            {
                "concept_title": concept_title,
                "primer": primer or "(none)",
                "existing_fronts": json.dumps(existing_fronts, separators=(",", ":")),
                "snippets": snippets,
                "max_cards": max_cards,
            },
            version=1,
        )
        raw = await self._client.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=_GENERATION_MAX_TOKENS,
        )
        return await _parse_or_repair(self, raw)

    async def repair(self, raw: str, error: str) -> str:
        repair_prompt = (
            "The following flashcard_generation JSON failed validation. Return ONLY "
            "corrected JSON (no markdown fences, no explanation) matching the shape "
            '{"cards": [{"front","back","hint","source_ref","card_type"}], '
            '"exhausted": bool, "reason": string}. Every card.source_ref must be a '
            "source_revision_id from the provided snippets.\n\n"
            f"ERROR: {error}\n\n"
            f"JSON:\n{raw}"
        )
        return await self._client.chat(
            [{"role": "user", "content": repair_prompt}],
            temperature=0.2,
            max_tokens=_GENERATION_MAX_TOKENS,
        )


# ---------------------------------------------------------------------------
# Public service entrypoints
# ---------------------------------------------------------------------------


async def stream_generate_deck(
    session: AsyncSession,
    generator: FlashcardGenerator,
    embedder: Embedder,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession],
    manager: FlashcardGenerationManager | None = None,
    extend: bool = False,
    force: bool = False,
) -> AsyncIterator[str]:
    """Yield SSE strings for flashcard generation.

    The actual generation runs in a detached background task that owns its own
    DB session, so a client disconnect never aborts persistence. The stream only
    subscribes for live status updates and the final deck payload.
    """
    try:
        await validate_concept_scope(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
        )
    except LookupError as exc:
        yield _sse("error", {"type": "error", "code": "not_found", "message": str(exc)})
        return

    if not extend and not force:
        existing = await _load_deck(session, workspace_id=workspace_id, concept_id=concept_id)
        if existing is not None:
            cards = await _load_cards(session, deck_id=existing.id)
            if cards:
                yield _sse(
                    "done",
                    {
                        "type": "done",
                        "deck": _deck_to_read(existing, cards).model_dump(mode="json"),
                        "exhausted": False,
                        "reason": "",
                    },
                )
                return

    await session.rollback()
    manager = manager or flashcard_generation_manager
    async for event in manager.stream(
        generator,
        embedder,
        session_factory,
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=concept_id,
        extend=extend,
        force=force,
    ):
        yield event


async def generate_deck(
    session: AsyncSession,
    generator: FlashcardGenerator,
    embedder: Embedder,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    extend: bool = False,
    force: bool = False,
) -> tuple[FlashcardDeckRead, bool, str]:
    """Generate (or extend) a concept's deck. Returns (deck_read, exhausted, reason).

    Single-flight: an advisory lock serializes concurrent PostgreSQL generators
    for the same concept (mirrors the quiz-draft lock).
    """
    _, concept = await validate_concept_scope(
        session, workspace_id=workspace_id, trail_id=trail_id, concept_id=concept_id
    )
    await _lock_deck_generation(session, concept_id=concept.id)

    deck = await _get_or_create_deck(
        session, workspace_id=workspace_id, trail_id=trail_id, concept=concept
    )
    existing = await _load_cards(session, deck_id=deck.id)

    # Idempotent: a populated deck with no force/extend is returned unchanged.
    if existing and not force and not extend:
        return _deck_to_read(deck, existing), False, ""

    if force:
        await session.execute(delete(Flashcard).where(Flashcard.deck_id == deck.id))
        await session.flush()
        existing = []

    snippets, allowed_refs, primer = await _load_grounding(
        session, workspace_id=workspace_id, concept=concept
    )
    if not allowed_refs:
        # No source material: never invent. Persist the (possibly empty) deck and
        # decline gracefully.
        await session.commit()
        cards = await _load_cards(session, deck_id=deck.id)
        return (
            _deck_to_read(deck, cards),
            True,
            "No linked source material to ground flashcards.",
        )

    existing_fronts = [card.front for card in existing]
    remaining_slots = max(0, DECK_SOFT_CAP - len(existing))
    if remaining_slots == 0:
        return _deck_to_read(deck, existing), True, "Deck is already at its soft cap."

    output = await generator.generate(
        concept_title=concept.title,
        primer=primer,
        existing_fronts=existing_fronts,
        snippets=snippets,
        max_cards=min(MAX_CARDS_PER_GENERATION, remaining_slots),
    )

    grounded = [card for card in output.cards if _is_grounded(card, allowed_refs)]
    deduped = await _drop_paraphrase_duplicates(
        grounded, existing_texts=[_card_text(c.front, c.back) for c in existing], embedder=embedder
    )
    accepted = deduped[: min(MAX_CARDS_PER_GENERATION, remaining_slots)]

    now = datetime.now(UTC)
    for card in accepted:
        session.add(
            Flashcard(
                deck_id=deck.id,
                workspace_id=workspace_id,
                front=card.front,
                back=card.back,
                hint=card.hint,
                source_ref=card.source_ref,
                card_type=card.card_type,
            )
        )
    deck.updated_at = now
    await session.commit()

    cards = await _load_cards(session, deck_id=deck.id)
    return _deck_to_read(deck, cards), output.exhausted, output.reason


async def get_deck(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
) -> FlashcardDeckRead:
    """Return the concept's deck + cards. Raises LookupError if no deck exists."""
    _, concept = await validate_concept_scope(
        session, workspace_id=workspace_id, trail_id=trail_id, concept_id=concept_id
    )
    deck = await _load_deck(session, workspace_id=workspace_id, concept_id=concept.id)
    if deck is None:
        raise LookupError(f"No flashcard deck for concept {concept_id}")
    cards = await _load_cards(session, deck_id=deck.id)
    return _deck_to_read(deck, cards)


async def review_card(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    card_id: uuid.UUID,
    recalled: bool,
) -> FlashcardRead:
    """Apply one Leitner recall-first swipe to a card and persist the new state."""
    _, concept = await validate_concept_scope(
        session, workspace_id=workspace_id, trail_id=trail_id, concept_id=concept_id
    )
    card = await session.scalar(
        select(Flashcard)
        .join(FlashcardDeck, FlashcardDeck.id == Flashcard.deck_id)
        .where(
            Flashcard.id == card_id,
            Flashcard.workspace_id == workspace_id,
            FlashcardDeck.concept_id == concept.id,
        )
    )
    if card is None:
        raise LookupError(f"Flashcard {card_id} not found")

    state = schedule_review(
        box=card.box,
        reps=card.reps,
        lapses=card.lapses,
        recalled=recalled,
        now=datetime.now(UTC),
    )
    card.box = state.box
    card.interval_days = state.interval_days
    card.last_reviewed = state.last_reviewed
    card.due = state.due
    card.reps = state.reps
    card.lapses = state.lapses
    await session.commit()
    return FlashcardRead.model_validate(card)


async def _produce_flashcard_events(
    session: AsyncSession,
    generator: FlashcardGenerator,
    embedder: Embedder,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    extend: bool,
    force: bool,
) -> AsyncIterator[str]:
    yield _sse("status", {"type": "status", "status": "generating"})
    try:
        deck, exhausted, reason = await generate_deck(
            session,
            generator,
            embedder,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            extend=extend,
            force=force,
        )
    except Exception as exc:
        logger.exception(
            "detached flashcard generation failed (workspace=%s trail=%s concept=%s)",
            workspace_id,
            trail_id,
            concept_id,
        )
        await session.rollback()
        code = "not_found" if isinstance(exc, LookupError) else "llm_error"
        yield _sse("error", {"type": "error", "code": code, "message": str(exc)})
        return

    yield _sse(
        "done",
        {
            "type": "done",
            "deck": deck.model_dump(mode="json"),
            "exhausted": exhausted,
            "reason": reason,
        },
    )


class _FlashcardJob:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.subscribers: set[asyncio.Queue[str | None]] = set()
        self.finished = False
        self.lock = asyncio.Lock()
        self.task: asyncio.Task[None] | None = None

    async def publish(self, event: str) -> None:
        async with self.lock:
            self.events.append(event)
            for queue in self.subscribers:
                queue.put_nowait(event)

    async def finish(self) -> None:
        async with self.lock:
            self.finished = True
            for queue in self.subscribers:
                queue.put_nowait(None)
            self.subscribers.clear()


class FlashcardGenerationManager:
    """Own detached, deduplicated flashcard generation tasks."""

    def __init__(self) -> None:
        self._jobs: dict[_FlashcardJobKey, _FlashcardJob] = {}
        self._lock = asyncio.Lock()

    async def stream(
        self,
        generator: FlashcardGenerator,
        embedder: Embedder,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        workspace_id: uuid.UUID,
        trail_id: uuid.UUID,
        concept_id: uuid.UUID,
        extend: bool,
        force: bool,
    ) -> AsyncIterator[str]:
        key = (workspace_id, trail_id, concept_id, extend, force)
        job = await self._ensure_job(
            key,
            generator,
            embedder,
            session_factory,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            extend=extend,
            force=force,
        )
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        async with job.lock:
            for event in job.events:
                queue.put_nowait(event)
            if job.finished:
                queue.put_nowait(None)
            else:
                job.subscribers.add(queue)
        try:
            while True:
                event = await queue.get()
                if event is None:
                    return
                yield event
        finally:
            async with job.lock:
                job.subscribers.discard(queue)

    async def _ensure_job(
        self,
        key: _FlashcardJobKey,
        generator: FlashcardGenerator,
        embedder: Embedder,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        workspace_id: uuid.UUID,
        trail_id: uuid.UUID,
        concept_id: uuid.UUID,
        extend: bool,
        force: bool,
    ) -> _FlashcardJob:
        async with self._lock:
            existing = self._jobs.get(key)
            if existing is not None and not existing.finished:
                return existing
            job = _FlashcardJob()
            self._jobs[key] = job
            job.task = asyncio.create_task(
                self._run(
                    key,
                    job,
                    generator,
                    embedder,
                    session_factory,
                    workspace_id=workspace_id,
                    trail_id=trail_id,
                    concept_id=concept_id,
                    extend=extend,
                    force=force,
                )
            )
            return job

    async def _run(
        self,
        key: _FlashcardJobKey,
        job: _FlashcardJob,
        generator: FlashcardGenerator,
        embedder: Embedder,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        workspace_id: uuid.UUID,
        trail_id: uuid.UUID,
        concept_id: uuid.UUID,
        extend: bool,
        force: bool,
    ) -> None:
        try:
            async with session_factory() as session:
                async for event in _produce_flashcard_events(
                    session,
                    generator,
                    embedder,
                    workspace_id=workspace_id,
                    trail_id=trail_id,
                    concept_id=concept_id,
                    extend=extend,
                    force=force,
                ):
                    await job.publish(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("detached flashcard generation failed for %s", key)
            await job.publish(
                _sse("error", {"type": "error", "code": "llm_error", "message": str(exc)})
            )
        finally:
            await job.finish()
            async with self._lock:
                if self._jobs.get(key) is job:
                    del self._jobs[key]

    async def shutdown(self) -> None:
        async with self._lock:
            tasks = [job.task for job in self._jobs.values() if job.task is not None]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task


flashcard_generation_manager = FlashcardGenerationManager()


# ---------------------------------------------------------------------------
# Grounding + dedup helpers
# ---------------------------------------------------------------------------


async def _load_grounding(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    concept: ConceptNode,
) -> tuple[str, set[str], str]:
    """Build (snippets_text, allowed_source_refs, primer_text) for a concept.

    Grounding chunks are the concept's linked source chunks (deterministic, not
    query-dependent). The allow-set is the set of contributing
    ``source_revision_id``s; cards must cite one of these.
    """
    rows = await session.execute(
        select(SourceRecord.title, SourceRevision.id, SourceChunk.text)
        .join(SourceRevision, SourceRevision.source_id == SourceRecord.id)
        .join(SourceChunk, SourceChunk.source_revision_id == SourceRevision.id)
        .join(ConceptSourceLink, ConceptSourceLink.source_id == SourceRecord.id)
        .where(
            ConceptSourceLink.concept_id == concept.id,
            SourceRecord.workspace_id == workspace_id,
            SourceRevision.workspace_id == workspace_id,
            SourceChunk.workspace_id == workspace_id,
        )
        .order_by(SourceRevision.id, SourceChunk.line_start)
        .limit(GROUNDING_CHUNK_LIMIT)
    )
    allowed_refs: set[str] = set()
    snippets: list[str] = []
    for title, revision_id, chunk_text in rows.all():
        ref = str(revision_id)
        allowed_refs.add(ref)
        body = (chunk_text or "").strip().replace("\n", " ")[:_SNIPPET_CHARS]
        snippets.append(f'[source_revision_id: {ref}] (from "{title}")\n{body}')

    primer = ""
    cached = read_cached_primer(concept)
    if cached is not None:
        terms = "; ".join(f"{t.term}: {t.definition}" for t in cached.key_terms)
        primer = f"{cached.overview}\nKey terms: {terms}".strip()

    return "\n\n".join(snippets), allowed_refs, primer


def _is_grounded(card: GeneratedCard, allowed_refs: set[str]) -> bool:
    return bool(card.source_ref) and card.source_ref in allowed_refs


async def _drop_paraphrase_duplicates(
    cards: list[GeneratedCard],
    *,
    existing_texts: list[str],
    embedder: Embedder,
) -> list[GeneratedCard]:
    """Drop new cards whose embedding is near-identical to a kept/existing card.

    Deterministic gate over cosine similarity. If embeddings are unavailable
    (disabled provider returns None) the gate is skipped — duplicates are still
    discouraged by feeding existing fronts back as exclusion context.
    """
    if not cards:
        return []
    new_texts = [_card_text(card.front, card.back) for card in cards]
    try:
        vectors = await embedder.embed(existing_texts + new_texts)
    except (OpenAIError, ValueError) as exc:
        logger.warning(
            "flashcard dedup embeddings unavailable; skipping similarity gate: %s: %s",
            exc.__class__.__name__,
            exc,
        )
        return cards
    if vectors is None:
        return cards

    existing_vecs = vectors[: len(existing_texts)]
    new_vecs = vectors[len(existing_texts) :]
    kept: list[GeneratedCard] = []
    kept_vecs: list[list[float]] = list(existing_vecs)
    for card, vector in zip(cards, new_vecs):
        if any(_cosine(vector, other) >= DEDUP_THRESHOLD for other in kept_vecs):
            continue
        kept.append(card)
        kept_vecs.append(vector)
    return kept


def _card_text(front: str, back: str) -> str:
    return f"{front} {back}".strip()


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


async def _get_or_create_deck(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept: ConceptNode,
) -> FlashcardDeck:
    deck = await _load_deck(session, workspace_id=workspace_id, concept_id=concept.id)
    if deck is not None:
        return deck
    deck = FlashcardDeck(
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=concept.id,
        title=f"{concept.title} flashcards",
    )
    session.add(deck)
    await session.flush()
    return deck


async def _load_deck(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
) -> FlashcardDeck | None:
    return await session.scalar(
        select(FlashcardDeck).where(
            FlashcardDeck.workspace_id == workspace_id,
            FlashcardDeck.concept_id == concept_id,
        )
    )


async def _load_cards(session: AsyncSession, *, deck_id: uuid.UUID) -> list[Flashcard]:
    return list(
        await session.scalars(
            select(Flashcard)
            .where(Flashcard.deck_id == deck_id)
            .order_by(Flashcard.created_at, Flashcard.id)
        )
    )


def _deck_to_read(deck: FlashcardDeck, cards: list[Flashcard]) -> FlashcardDeckRead:
    return FlashcardDeckRead(
        id=deck.id,
        workspace_id=deck.workspace_id,
        trail_id=deck.trail_id,
        concept_id=deck.concept_id,
        title=deck.title,
        created_at=deck.created_at,
        updated_at=deck.updated_at,
        cards=[FlashcardRead.model_validate(card) for card in cards],
    )


async def _lock_deck_generation(session: AsyncSession, *, concept_id: uuid.UUID) -> None:
    connection = await session.connection()
    if connection.dialect.name != "postgresql":
        return
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": _deck_lock_key(concept_id)},
    )


def _deck_lock_key(concept_id: uuid.UUID) -> int:
    digest = blake2b(f"flashcards:{concept_id}".encode("ascii"), digest_size=8).digest()
    return int.from_bytes(digest, "big") & 0x7FFFFFFFFFFFFFFF


def _sse(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def _parse_flashcard_output(raw: str) -> FlashcardGenerationOutput:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise FlashcardGenerationError(
            f"Flashcard generation returned invalid JSON: {exc}"
        ) from exc
    try:
        return FlashcardGenerationOutput.model_validate(data)
    except Exception as exc:
        raise FlashcardGenerationError(f"Flashcard generation failed validation: {exc}") from exc


async def _parse_or_repair(
    generator: FlashcardGenerator,
    raw: str,
) -> FlashcardGenerationOutput:
    """Parse generator JSON, falling back to EXACTLY ONE repair attempt."""
    try:
        return _parse_flashcard_output(raw)
    except FlashcardGenerationError as exc:
        repair = getattr(generator, "repair", None)
        if repair is None:
            raise
        repaired = await repair(raw, str(exc))
        try:
            return _parse_flashcard_output(repaired)
        except FlashcardGenerationError as repair_exc:
            raise FlashcardGenerationError(
                f"Flashcard generation failed validation after repair: {repair_exc}"
            ) from repair_exc
