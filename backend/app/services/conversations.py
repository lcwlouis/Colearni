"""Conversation persistence service.

Handles get-or-create conversation, scope validation, context assembly, and
conversation history retrieval.

Known limitations:
- Automatic conversation summarisation is deferred; the conversation_summaries
  table is created and the model is wired, but no summary is generated yet.
  Context always falls back to the last N raw turns.
- On LLM generation failure, the user turn is NOT persisted (the whole
  transaction is rolled back). This differs from the API spec note that "user
  turn may remain persisted"; we prefer clean state. Documented here as a known
  deviation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.conversation import (
    Conversation,
    ConversationSummary,
    ConversationTurn,
)
from backend.app.models.source import ConceptSourceLink, SourceRecord
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.services.mastery import get_mastery_state
from backend.app.services.retrieval import get_concept_sources_for_tutor, get_graph_neighbourhood

# Maximum number of recent visible turns included in the prompt context window.
_RECENT_VISIBLE_TURNS_LIMIT = 10


@dataclass
class TutorSourceMetadata:
    """Safe, whitelisted source metadata included in tutor context.

    Public and private-access linked sources are represented here.
    No raw content, chunks, embeddings, private notes, or source-derived
    summaries are included — metadata only.

    Whitelisted fields: id, title, url, origin, access, license, relation.
    """

    id: uuid.UUID
    title: str
    url: str | None
    origin: str
    access: str
    license: str | None
    relation: str


@dataclass
class TutorContext:
    """All data needed by the tutor agent and instruction tool."""

    conversation_id: uuid.UUID
    concept: ConceptNode
    trail: Trail
    learner_message: str
    user_turn_index: int

    prerequisites: list[ConceptNode] = field(default_factory=list)
    contained_nodes: list[ConceptNode] = field(default_factory=list)
    containing_nodes: list[ConceptNode] = field(default_factory=list)
    related: list[ConceptNode] = field(default_factory=list)
    application_nodes: list[ConceptNode] = field(default_factory=list)

    mastery_status: str = "not_started"

    recent_turns: list[ConversationTurn] = field(default_factory=list)
    conversation_summary: ConversationSummary | None = None

    # Safe linked source metadata for the current concept.
    # Populated by get_concept_sources_for_tutor; empty when no allowed sources are linked.
    sources: list[TutorSourceMetadata] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Scope validation helpers
# ---------------------------------------------------------------------------


async def validate_concept_scope(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
) -> tuple[Trail, ConceptNode]:
    """Verify workspace → trail → concept hierarchy.

    Raises LookupError with a descriptive message if any level is missing or
    mis-scoped.  Returns (trail, concept) on success so callers can reuse them.
    """
    if await session.get(Workspace, workspace_id) is None:
        raise LookupError(f"Workspace {workspace_id} not found")

    trail = await session.scalar(
        select(Trail).where(Trail.id == trail_id, Trail.workspace_id == workspace_id)
    )
    if trail is None:
        raise LookupError(f"Trail {trail_id} not found")

    concept = await session.scalar(
        select(ConceptNode).where(ConceptNode.id == concept_id, ConceptNode.trail_id == trail_id)
    )
    if concept is None:
        raise LookupError(f"Concept {concept_id} not found")

    return trail, concept


# ---------------------------------------------------------------------------
# Core conversation helpers
# ---------------------------------------------------------------------------


async def get_or_create_conversation(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    conversation_id: uuid.UUID | None = None,
) -> Conversation:
    """Return the conversation for this workspace/trail/concept, creating it if
    it does not exist.

    If *conversation_id* is provided, it is verified to belong to the same
    workspace/trail/concept.  A mismatch raises LookupError (→ 404 in routes).
    """
    # Validate scope and confirm concept belongs to trail.
    trail, concept = await validate_concept_scope(
        session,
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=concept_id,
    )

    # If a specific conversation_id was supplied, validate its scope.
    if conversation_id is not None:
        conv = await session.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.workspace_id == workspace_id,
                Conversation.trail_id == trail_id,
                Conversation.concept_id == concept_id,
            )
        )
        if conv is None:
            raise LookupError(f"Conversation {conversation_id} not found for this concept")
        return conv

    # Look up (or create) the single conversation for this workspace/trail/concept.
    existing = await session.scalar(
        select(Conversation).where(
            Conversation.workspace_id == workspace_id,
            Conversation.trail_id == trail_id,
            Conversation.concept_id == concept_id,
        )
    )
    if existing is not None:
        return existing

    new_conv = Conversation(
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=concept_id,
    )
    session.add(new_conv)
    await session.flush()
    return new_conv


async def build_tutor_context(
    session: AsyncSession,
    *,
    conversation: Conversation,
    concept: ConceptNode,
    trail: Trail,
    learner_message: str,
    user_turn_index: int,
) -> TutorContext:
    """Assemble graph context, recent conversation history, and mastery state.

    Retrieval order follows docs/TUTOR_BEHAVIOUR.md:
      1. Current concept.
      2. Prerequisites.
      3. Containing / contained nodes.
      4. Related / application nodes.
      5. Trail topic and goal.
      6. Public and private-access linked source metadata for the current concept.
      7. Recent conversation turns (last RECENT_TURNS_LIMIT).
      8. Conversation summary (if present).

    Deliberately does NOT search the whole workspace or include sources from
    other workspaces. Private sources from the current workspace are included
    (access == "public" or "private"); restricted and unknown are excluded.
    """
    # --- Load all edges for this trail once (cheap, bounded by trail size) ---
    all_nodes = list(
        await session.scalars(select(ConceptNode).where(ConceptNode.trail_id == trail.id))
    )

    edges = list(await session.scalars(select(ConceptEdge).where(ConceptEdge.trail_id == trail.id)))

    neighbourhood = get_graph_neighbourhood(
        concept=concept,
        all_nodes=all_nodes,
        edges=edges,
    )

    # --- Conversation history ---
    # Keep the visible history window bounded, but preserve internal tool turns
    # that occurred within that retained visible window so gated-mode context
    # remains replayable on later turns.
    visible_rows = list(
        await session.scalars(
            select(ConversationTurn)
            .where(
                ConversationTurn.conversation_id == conversation.id,
                ConversationTurn.turn_index < user_turn_index,
                ConversationTurn.kind == "visible",
            )
            .order_by(ConversationTurn.turn_index.desc())
            .limit(_RECENT_VISIBLE_TURNS_LIMIT)
        )
    )
    recent_turns = list(reversed(visible_rows))

    if recent_turns:
        earliest_visible_turn_index = recent_turns[0].turn_index
        tool_rows = list(
            await session.scalars(
                select(ConversationTurn)
                .where(
                    ConversationTurn.conversation_id == conversation.id,
                    ConversationTurn.turn_index >= earliest_visible_turn_index,
                    ConversationTurn.turn_index < user_turn_index,
                    ConversationTurn.kind != "visible",
                )
                .order_by(ConversationTurn.turn_index.asc())
            )
        )
        if tool_rows:
            merged_turns = {turn.turn_index: turn for turn in recent_turns}
            for turn in tool_rows:
                merged_turns[turn.turn_index] = turn
            recent_turns = [merged_turns[index] for index in sorted(merged_turns)]

    # --- Conversation summary (most recent) ---
    summary = await session.scalar(
        select(ConversationSummary)
        .where(ConversationSummary.conversation_id == conversation.id)
        .order_by(ConversationSummary.turns_covered_to.desc())
        .limit(1)
    )

    mastery_state = await get_mastery_state(
        session,
        workspace_id=trail.workspace_id,
        concept=concept,
    )

    return TutorContext(
        conversation_id=conversation.id,
        concept=concept,
        trail=trail,
        learner_message=learner_message,
        user_turn_index=user_turn_index,
        prerequisites=neighbourhood["prerequisites"],
        contained_nodes=neighbourhood["contained_nodes"],
        containing_nodes=neighbourhood["containing_nodes"],
        related=neighbourhood["related"],
        application_nodes=neighbourhood["application_nodes"],
        mastery_status=mastery_state.status,
        recent_turns=recent_turns,
        conversation_summary=summary,
        sources=await get_concept_sources_for_tutor(
            session,
            workspace_id=trail.workspace_id,
            concept_id=concept.id,
            max_sources=10,
        ),
    )


async def get_conversation_history(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    limit: int = 20,
) -> tuple[uuid.UUID | None, list[ConversationTurn]]:
    """Return conversation_id (or None) and up to *limit* turns in chronological order.

    Validates scope; raises LookupError if workspace/trail/concept is invalid.
    Returns (None, []) if no conversation has started for this concept yet.
    """
    limit = min(max(1, limit), 100)

    await validate_concept_scope(
        session,
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=concept_id,
    )

    conv = await session.scalar(
        select(Conversation).where(
            Conversation.workspace_id == workspace_id,
            Conversation.trail_id == trail_id,
            Conversation.concept_id == concept_id,
        )
    )
    if conv is None:
        return None, []

    # Fetch the most recent turns, then restore chronological order for the API.
    recent_turns = list(
        await session.scalars(
            select(ConversationTurn)
            .where(
                ConversationTurn.conversation_id == conv.id,
                ConversationTurn.kind == "visible",
            )
            .order_by(ConversationTurn.turn_index.desc())
            .limit(limit)
        )
    )
    return conv.id, list(reversed(recent_turns))


async def get_next_turn_index(session: AsyncSession, conversation_id: uuid.UUID) -> int:
    """Return the next sequential turn_index for a conversation."""
    from sqlalchemy import func

    max_index = await session.scalar(
        select(func.max(ConversationTurn.turn_index)).where(
            ConversationTurn.conversation_id == conversation_id
        )
    )
    return (max_index if max_index is not None else -1) + 1


async def persist_user_turn(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    content: str,
    turn_index: int,
) -> ConversationTurn:
    """Add the user turn to the session (flushed, not committed)."""
    turn = ConversationTurn(
        conversation_id=conversation_id,
        role="user",
        kind="visible",
        content=content,
        mode=None,
        turn_index=turn_index,
    )
    session.add(turn)
    await session.flush()
    return turn


async def persist_assistant_turn(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    content: str,
    mode: str,
    turn_index: int,
    reasoning: str | None = None,
    reasoning_parts: list[dict] | None = None,
) -> ConversationTurn:
    """Add the assistant turn, optional reasoning trace, and commit."""
    turn = ConversationTurn(
        conversation_id=conversation_id,
        role="assistant",
        kind="visible",
        content=content,
        reasoning=reasoning,
        reasoning_parts=reasoning_parts,
        mode=mode,
        turn_index=turn_index,
    )
    session.add(turn)

    # Touch conversation.updated_at explicitly (no server-side onupdate).
    conv = await session.get(Conversation, conversation_id)
    if conv is not None:
        conv.updated_at = datetime.now(UTC)

    await session.commit()
    return turn


async def persist_tool_turn(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    *,
    role: str,
    kind: str,
    content: str,
    turn_index: int,
    mode: str | None = None,
) -> ConversationTurn:
    """Persist an internal tool call/result turn for prompt replay.

    Tool turns are excluded from the public history API but remain part of the
    prompt history so prior tool uses stay cacheable on later turns.
    """
    turn = ConversationTurn(
        conversation_id=conversation_id,
        role=role,
        kind=kind,
        content=content,
        reasoning=None,
        reasoning_parts=None,
        mode=mode,
        turn_index=turn_index,
    )
    session.add(turn)
    await session.flush()
    return turn


# ---------------------------------------------------------------------------
# Safe source metadata loader
# ---------------------------------------------------------------------------


async def _load_safe_sources(
    session: AsyncSession,
    *,
    concept_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> list[TutorSourceMetadata]:
    """Load whitelisted source metadata for tutor context.

    Legacy public-only helper kept for direct provenance unit tests. New code
    should use get_concept_sources_for_tutor so private linked uploads are
    visible to the tutor under the current retrieval policy.

    Safety rules enforced here (see docs/SOURCE_PROVENANCE.md):
      - Only sources linked to the current concept via ConceptSourceLink.
      - Only sources belonging to the same workspace.
      - Only access == "public"  (private/restricted/unknown are excluded).
      - Exclude origin == "user_upload"  (user uploads stay private).
      - Metadata only — never raw text, chunks, embeddings, or summaries.

    The tutor may cite returned sources by title; it must not claim to have
    read content from any other source.
    """
    rows = list(
        await session.execute(
            select(ConceptSourceLink.relation, SourceRecord)
            .join(SourceRecord, ConceptSourceLink.source_id == SourceRecord.id)
            .where(
                ConceptSourceLink.concept_id == concept_id,
                SourceRecord.workspace_id == workspace_id,
                SourceRecord.access == "public",
                SourceRecord.origin != "user_upload",
            )
        )
    )
    return [
        TutorSourceMetadata(
            id=src.id,
            title=src.title,
            url=src.url,
            origin=src.origin,
            access=src.access,
            license=src.license,
            relation=relation,
        )
        for relation, src in rows
    ]
