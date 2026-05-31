from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.artifact import Artifact
from backend.app.models.concept import ConceptNode
from backend.app.models.flashcard import Flashcard, FlashcardDeck
from backend.app.models.mastery import QuizAttempt
from backend.app.models.pin import Pin
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.artifact import ArtifactRead
from backend.app.schemas.flashcard import FlashcardDeckRead, FlashcardRead
from backend.app.schemas.pin import ConceptPinItem, PinItemType, PinListResponse
from backend.app.services.quizzes import _attempt_to_read


async def _validate_trail_scope(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
) -> None:
    """Verify the workspace → trail hierarchy. Raises LookupError on mismatch."""
    if await session.get(Workspace, workspace_id) is None:
        raise LookupError(f"Workspace {workspace_id} not found")
    trail = await session.scalar(
        select(Trail).where(Trail.id == trail_id, Trail.workspace_id == workspace_id)
    )
    if trail is None:
        raise LookupError(f"Trail {trail_id} not found")


async def _item_belongs_to_trail(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    item_type: PinItemType,
    item_id: uuid.UUID,
) -> bool:
    """Whether the referenced item exists within this workspace + trail.

    Prevents cross-trail / cross-workspace pinning. Artifacts are directly
    workspace+trail scoped; quiz attempts are concept-scoped, so we join through
    the concept to confirm trail membership. Flashcard pins reference a deck id
    (the deck is the retrievable unit, like a quiz attempt).
    """
    if item_type == "artifact":
        artifact = await session.scalar(
            select(Artifact.id).where(
                Artifact.id == item_id,
                Artifact.workspace_id == workspace_id,
                Artifact.trail_id == trail_id,
            )
        )
        return artifact is not None

    if item_type == "flashcard":
        deck = await session.scalar(
            select(FlashcardDeck.id).where(
                FlashcardDeck.id == item_id,
                FlashcardDeck.workspace_id == workspace_id,
                FlashcardDeck.trail_id == trail_id,
            )
        )
        return deck is not None

    if item_type == "concept":
        concept = await session.scalar(
            select(ConceptNode.id).where(
                ConceptNode.id == item_id,
                ConceptNode.trail_id == trail_id,
            )
        )
        return concept is not None

    attempt = await session.scalar(
        select(QuizAttempt.id)
        .join(ConceptNode, ConceptNode.id == QuizAttempt.concept_id)
        .where(QuizAttempt.id == item_id, ConceptNode.trail_id == trail_id)
    )
    return attempt is not None


async def pin_item(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    item_type: PinItemType,
    item_id: uuid.UUID,
) -> None:
    """Idempotently pin an item to a trail.

    Validates the item belongs to the same workspace+trail (no cross-trail
    pins). A second pin of the same item is a no-op (enforced by the unique
    constraint; an existing row short-circuits before insert).
    """
    await _validate_trail_scope(session, workspace_id=workspace_id, trail_id=trail_id)
    if not await _item_belongs_to_trail(
        session,
        workspace_id=workspace_id,
        trail_id=trail_id,
        item_type=item_type,
        item_id=item_id,
    ):
        raise LookupError(f"{item_type} {item_id} not found in this trail")

    existing = await session.scalar(
        select(Pin.id).where(
            Pin.workspace_id == workspace_id,
            Pin.trail_id == trail_id,
            Pin.item_type == item_type,
            Pin.item_id == item_id,
        )
    )
    if existing is not None:
        return

    session.add(
        Pin(
            workspace_id=workspace_id,
            trail_id=trail_id,
            item_type=item_type,
            item_id=item_id,
        )
    )
    try:
        await session.commit()
    except IntegrityError:
        # Lost a race against a concurrent pin of the same item; the unique
        # constraint guarantees idempotency, so treat as already pinned.
        await session.rollback()


async def unpin_item(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    item_type: PinItemType,
    item_id: uuid.UUID,
) -> None:
    """Idempotently unpin an item; a no-op if it is not pinned."""
    await _validate_trail_scope(session, workspace_id=workspace_id, trail_id=trail_id)
    pin = await session.scalar(
        select(Pin).where(
            Pin.workspace_id == workspace_id,
            Pin.trail_id == trail_id,
            Pin.item_type == item_type,
            Pin.item_id == item_id,
        )
    )
    if pin is None:
        return
    await session.delete(pin)
    await session.commit()


async def list_pins(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
) -> PinListResponse:
    """Aggregate pinned artifacts + quiz attempts for a trail.

    Bounded to a single workspace+trail; joins pins -> artifacts / quiz_attempts.
    Pins whose target row no longer exists (or fell out of scope) are excluded.
    """
    await _validate_trail_scope(session, workspace_id=workspace_id, trail_id=trail_id)

    artifact_rows = list(
        await session.scalars(
            select(Artifact)
            .join(
                Pin,
                (Pin.item_id == Artifact.id) & (Pin.item_type == "artifact"),
            )
            .where(Pin.workspace_id == workspace_id, Pin.trail_id == trail_id)
            .order_by(Pin.pinned_at.desc())
        )
    )

    attempt_rows = list(
        await session.scalars(
            select(QuizAttempt)
            .join(ConceptNode, ConceptNode.id == QuizAttempt.concept_id)
            .join(
                Pin,
                (Pin.item_id == QuizAttempt.id) & (Pin.item_type == "quiz_attempt"),
            )
            .where(
                Pin.workspace_id == workspace_id,
                Pin.trail_id == trail_id,
                ConceptNode.trail_id == trail_id,
            )
            .order_by(Pin.pinned_at.desc())
        )
    )

    return PinListResponse(
        artifacts=[ArtifactRead.model_validate(artifact) for artifact in artifact_rows],
        quiz_attempts=[_attempt_to_read(attempt) for attempt in attempt_rows],
        flashcards=await _pinned_flashcard_decks(
            session, workspace_id=workspace_id, trail_id=trail_id
        ),
        concepts=await _pinned_concepts(
            session, workspace_id=workspace_id, trail_id=trail_id
        ),
    )


async def _pinned_flashcard_decks(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
) -> list[FlashcardDeckRead]:
    """Resolve pinned flashcard decks (+ their cards) scoped to the trail."""
    decks = list(
        await session.scalars(
            select(FlashcardDeck)
            .join(
                Pin,
                (Pin.item_id == FlashcardDeck.id) & (Pin.item_type == "flashcard"),
            )
            .where(
                Pin.workspace_id == workspace_id,
                Pin.trail_id == trail_id,
                FlashcardDeck.trail_id == trail_id,
            )
            .order_by(Pin.pinned_at.desc())
        )
    )
    reads: list[FlashcardDeckRead] = []
    for deck in decks:
        cards = list(
            await session.scalars(
                select(Flashcard)
                .where(Flashcard.deck_id == deck.id)
                .order_by(Flashcard.created_at, Flashcard.id)
            )
        )
        reads.append(
            FlashcardDeckRead(
                id=deck.id,
                workspace_id=deck.workspace_id,
                trail_id=deck.trail_id,
                concept_id=deck.concept_id,
                title=deck.title,
                created_at=deck.created_at,
                updated_at=deck.updated_at,
                cards=[FlashcardRead.model_validate(card) for card in cards],
            )
        )
    return reads


async def _pinned_concepts(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
) -> list[ConceptPinItem]:
    """Return concept pins for a workspace+trail scope."""
    stmt = (
        select(Pin, ConceptNode, Trail)
        .join(ConceptNode, ConceptNode.id == Pin.item_id)
        .join(Trail, Trail.id == ConceptNode.trail_id)
        .where(
            Pin.workspace_id == workspace_id,
            Pin.trail_id == trail_id,
            Pin.item_type == "concept",
        )
    )
    rows = (await session.execute(stmt)).all()
    return [
        ConceptPinItem(
            concept_id=row.ConceptNode.id,
            concept_title=row.ConceptNode.title,
            trail_id=row.Trail.id,
            trail_title=row.Trail.title,
        )
        for row in rows
    ]
