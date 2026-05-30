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

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.provider_tools import NormalizedToolCall, NormalizedToolResult
from backend.app.agents.retrieval_tools import (  # noqa: F401
    READ_DOCUMENT_SECTION_TOOL,
    RETRIEVAL_TOOLS,
)
from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.conversation import (
    Conversation,
    ConversationSummary,
    ConversationTurn,
)
from backend.app.models.source import ConceptSourceLink, SourceRecord
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.concept import ConceptPrimerRead
from backend.app.services.mastery import get_mastery_state
from backend.app.services.reranker import ChunkSearchResult  # noqa: F401
from backend.app.services.retrieval import (
    get_concept_sources_for_tutor,
    get_graph_neighbourhood,
    read_document_section,
    search_sources_by_text,
)
from backend.app.settings import settings


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

    # Optional learner-supplied prior knowledge captured at Trail creation
    # (Phase 13.5d). Read-only signal that helps the tutor calibrate how quickly
    # it shifts from exposition to Socratic questioning. Composable with the
    # 13.5b opening move. Adaptive write-back belongs to Phase 13.
    prior_knowledge: str | None = None

    # True on the learner's first substantive turn for this concept: no prior visible
    # assistant turn exists and mastery is still early. Drives the worked-example-first
    # opening move (Phase 13.5b). Composable with future prior-knowledge signals (13.5d).
    is_opening_turn: bool = False

    # Opportunistically attached cached concept primer (overview + key terms), if one
    # has already been generated. Never force-generated here.
    primer: ConceptPrimerRead | None = None

    recent_turns: list[ConversationTurn] = field(default_factory=list)
    conversation_summary: ConversationSummary | None = None

    # Safe linked source metadata for the current concept.
    # Populated by get_concept_sources_for_tutor; empty when no allowed sources are linked.
    sources: list[TutorSourceMetadata] = field(default_factory=list)


@dataclass(frozen=True)
class RetrievalLoopResult:
    messages: list[dict]
    tool_results: list[NormalizedToolResult]
    text: str = ""
    thinking: str = ""

    def __iter__(self):
        yield self.messages
        yield self.tool_results


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
            .limit(settings.tutor_recent_visible_turns_limit)
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

    # Opening-turn detection (Phase 13.5b): deterministically true when this concept's
    # conversation has no prior visible assistant turn and mastery is still early. Passed
    # explicitly into the prompt context rather than letting the model guess.
    has_prior_assistant_turn = any(turn.role == "assistant" for turn in recent_turns)
    is_opening_turn = (not has_prior_assistant_turn) and mastery_state.status in {
        "not_started",
        "learning",
    }

    # Local import avoids a module-level circular import (concept_primers imports
    # validate_concept_scope from this module). read_cached_primer is a pure read of
    # concept.metadata_json and never triggers generation.
    from backend.app.services.concept_primers import read_cached_primer

    primer = read_cached_primer(concept) if is_opening_turn else None

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
        prior_knowledge=trail.prior_knowledge,
        is_opening_turn=is_opening_turn,
        primer=primer,
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


async def prepare_regenerated_user_turn(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    content: str,
) -> ConversationTurn:
    """Reuse the latest visible user turn and remove generated turns after it.

    Regenerate should replace the assistant response to a user message, not append
    a duplicate user turn or include the old assistant answer in prompt context.
    """
    user_turn = await session.scalar(
        select(ConversationTurn)
        .where(
            ConversationTurn.conversation_id == conversation_id,
            ConversationTurn.role == "user",
            ConversationTurn.kind == "visible",
        )
        .order_by(ConversationTurn.turn_index.desc())
        .limit(1)
    )
    if user_turn is None:
        raise LookupError("Cannot regenerate before a user turn exists")
    if user_turn.content.strip() != content.strip():
        raise ValueError("Regenerate message does not match the latest user turn")

    await session.execute(
        delete(ConversationTurn).where(
            ConversationTurn.conversation_id == conversation_id,
            ConversationTurn.turn_index > user_turn.turn_index,
        )
    )
    await session.flush()
    return user_turn


async def replace_latest_user_turn(
    session: AsyncSession,
    conversation_id: uuid.UUID,
    content: str,
) -> ConversationTurn:
    """Replace the latest visible user turn and delete generated turns after it."""
    user_turn = await session.scalar(
        select(ConversationTurn)
        .where(
            ConversationTurn.conversation_id == conversation_id,
            ConversationTurn.role == "user",
            ConversationTurn.kind == "visible",
        )
        .order_by(ConversationTurn.turn_index.desc())
        .limit(1)
    )
    if user_turn is None:
        raise LookupError("Cannot edit before a user turn exists")

    user_turn.content = content
    await session.execute(
        delete(ConversationTurn).where(
            ConversationTurn.conversation_id == conversation_id,
            ConversationTurn.turn_index > user_turn.turn_index,
        )
    )
    await session.flush()
    return user_turn


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

# Tool call result truncation and directed-retrieval tooling constants.
#
# A "directed" retrieval tool returns self-contained context that fully grounds
# the next answer, so once one succeeds we stop the retrieval loop instead of
# making another planner call. That extra planner call would otherwise generate a
# complete answer under the planning prompt that we then DISCARD before the clean,
# streamed final response runs — i.e. a wasted 4th LLM call per turn.
#
# - read_document_section: returns the requested document section.
# - get_concept_primer / get_graph_neighbourhood: each return complete
#   concept-level orientation that needs no follow-up tool. On a source-less
#   concept these are the only tools offered, so leaving them out of this set is
#   what produced the redundant round-2 generation.
#
# Source discovery tools (search_sources, get_concept_sources) are intentionally
# NOT directed: the model may legitimately follow them with read_document_section
# in a later round.
_DIRECTED_RETRIEVAL_TOOLS = {
    "read_document_section",
    "get_concept_primer",
    "get_graph_neighbourhood",
}


def _truncate_tool_result(content: str) -> str:
    cap = settings.tutor_max_tool_result_chars
    if len(content) <= cap:
        return content
    return content[:cap] + " ... [truncated]"


def _is_directed_retrieval_result(result: NormalizedToolResult) -> bool:
    return (
        result.name in _DIRECTED_RETRIEVAL_TOOLS and not result.is_error and result.content.strip()
    )


def _format_chunk_results(results: list[ChunkSearchResult]) -> str:
    """Format ChunkSearchResult list for LLM context. Includes line navigation hints."""
    if not results:
        return "No matching chunks found."
    parts = []
    for r in results:
        heading = f" (section: {r.section_heading})" if r.section_heading else ""
        parts.append(
            f"Source: {r.source_title}{heading}\n"
            f"Lines {r.line_start}–{r.line_end} | revision: {r.source_revision_id}\n"
            f"{r.chunk_text[:500]}"
        )
    return "\n\n---\n\n".join(parts)


def _format_source_list(sources: list[TutorSourceMetadata]) -> str:
    if not sources:
        return "No sources linked to this concept."
    return "\n".join(f"- {s.title} [{s.relation}] ({s.origin}, {s.access})" for s in sources)


def _format_primer_result(primer: ConceptPrimerRead) -> str:
    """Render a cached primer as compact, export-safe orientation text.

    Primer content is abstract concept-level orientation (not source-derived), so it
    is safe to surface in tool results without sanitiser changes.
    """
    lines = [f"Overview: {primer.overview}"]
    if primer.key_terms:
        lines.append("Key terms:")
        lines.extend(f"- {term.term}: {term.definition}" for term in primer.key_terms)
    if primer.sample_questions:
        lines.append("Sample starter questions:")
        lines.extend(f"- {question}" for question in primer.sample_questions)
    return "\n".join(lines)


async def _get_primer_for_concept(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
) -> str:
    """Read the cached primer for a concept and format it, scoped to the workspace.

    Read-only and cheap: never triggers primer generation. Returns a short
    "no primer available" message when nothing is cached so the loop can continue.
    """
    # Local import avoids a module-level circular import (concept_primers imports
    # validate_concept_scope from this module). read_cached_primer is a pure read.
    from backend.app.services.concept_primers import read_cached_primer

    concept = await session.scalar(select(ConceptNode).where(ConceptNode.id == concept_id))
    if concept is None:
        return f"Concept {concept_id} not found."

    trail = await session.scalar(
        select(Trail).where(
            Trail.id == concept.trail_id,
            Trail.workspace_id == workspace_id,
        )
    )
    if trail is None:
        return f"Concept {concept_id} not found in this workspace."

    primer = read_cached_primer(concept)
    if primer is None:
        return "No primer available yet for this concept."
    return _format_primer_result(primer)


async def _get_neighbourhood_for_concept(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
) -> str:
    """Load graph neighbourhood for a concept and return a formatted string."""
    from sqlalchemy import select as _select

    from backend.app.models.concept import (  # noqa: PLC0415
        ConceptEdge as _ConceptEdge,
    )
    from backend.app.models.concept import (
        ConceptNode as _ConceptNode,
    )
    from backend.app.models.trail import Trail as _Trail

    concept = await session.scalar(_select(_ConceptNode).where(_ConceptNode.id == concept_id))
    if concept is None:
        return f"Concept {concept_id} not found."

    trail = await session.scalar(
        _select(_Trail).where(
            _Trail.id == concept.trail_id,
            _Trail.workspace_id == workspace_id,
        )
    )
    if trail is None:
        return f"Concept {concept_id} not found in this workspace."

    all_nodes = list(
        await session.scalars(_select(_ConceptNode).where(_ConceptNode.trail_id == trail.id))
    )
    edges = list(
        await session.scalars(_select(_ConceptEdge).where(_ConceptEdge.trail_id == trail.id))
    )
    neighbourhood = get_graph_neighbourhood(
        concept=concept,
        all_nodes=all_nodes,
        edges=edges,
    )
    parts = []
    for key, nodes in neighbourhood.items():
        if nodes:
            titles = ", ".join(n.title for n in nodes)
            parts.append(f"{key}: {titles}")
    return "\n".join(parts) if parts else "No neighbours found."


async def execute_retrieval_tool(
    tool_call: NormalizedToolCall,
    *,
    session: AsyncSession,
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
) -> NormalizedToolResult:
    """Dispatch a retrieval tool call and return a normalized result.

    Enforces workspace scope on all calls. Returns an error result on
    any exception — does not re-raise (the loop continues safely).
    """
    try:
        if not tool_call.is_valid:
            raise ValueError(f"Invalid tool arguments: {tool_call.validation_error}")

        if tool_call.name == "search_sources":
            query = tool_call.arguments["query"]
            results = await search_sources_by_text(
                query=query,
                workspace_id=workspace_id,
                session=session,
                concept_id=concept_id,
            )
            content = _format_chunk_results(results)

        elif tool_call.name == "get_concept_sources":
            cid = _tool_concept_id(tool_call, concept_id)
            sources = await get_concept_sources_for_tutor(
                session=session,
                workspace_id=workspace_id,
                concept_id=cid,
            )
            content = _format_source_list(sources)

        elif tool_call.name == "get_graph_neighbourhood":
            cid = _tool_concept_id(tool_call, concept_id)
            content = await _get_neighbourhood_for_concept(session, workspace_id, cid)

        elif tool_call.name == "get_concept_primer":
            cid = _tool_concept_id(tool_call, concept_id)
            content = await _get_primer_for_concept(session, workspace_id, cid)

        elif tool_call.name == "read_document_section":
            rev_id = uuid.UUID(tool_call.arguments["source_revision_id"])
            line_start = int(tool_call.arguments["line_start"])
            window_lines = int(tool_call.arguments.get("window_lines", 50))
            content = await read_document_section(
                session=session,
                workspace_id=workspace_id,
                source_revision_id=rev_id,
                line_start=line_start,
                window_lines=window_lines,
            )

        else:
            content = f"Unknown tool: {tool_call.name}"

    except Exception as exc:
        return NormalizedToolResult(
            call_id=tool_call.call_id,
            name=tool_call.name,
            content=f"Tool error: {exc}",
            is_error=True,
            public_preview={"error": str(exc)},
        )

    content = _truncate_tool_result(content)
    return NormalizedToolResult(
        call_id=tool_call.call_id,
        name=tool_call.name,
        content=content,
        public_preview=_public_retrieval_preview(tool_call, content),
    )


def _public_retrieval_preview(tool_call: NormalizedToolCall, content: str) -> dict[str, str]:
    preview = {"preview": content[:200]}
    if tool_call.name == "search_sources" and isinstance(tool_call.arguments.get("query"), str):
        preview["query"] = tool_call.arguments["query"]
    return preview


def _tool_concept_id(tool_call: NormalizedToolCall, current_concept_id: uuid.UUID) -> uuid.UUID:
    raw_concept_id = tool_call.arguments.get("concept_id")
    if not raw_concept_id:
        return current_concept_id
    try:
        return uuid.UUID(str(raw_concept_id))
    except ValueError:
        return current_concept_id


def _append_tool_round(
    messages: list[dict],
    tool_calls: list[NormalizedToolCall],
    results: list[NormalizedToolResult],
) -> list[dict]:
    """Append a tool round (assistant tool_calls + tool results) to messages.

    Follows the same OpenAI Chat Completions wire format used internally
    by the tutor continuation (provider-neutral tagged assistant messages).
    """
    # Build assistant message content describing the tool calls
    tool_call_content = json.dumps(
        [
            {
                "type": "tool_call",
                "id": tc.call_id,
                "name": tc.name,
                "arguments": tc.arguments,
            }
            for tc in tool_calls
        ]
    )
    new_messages = list(messages)
    new_messages.append({"role": "assistant", "content": tool_call_content})
    # Add one tool result message per result
    for result in results:
        new_messages.append(
            {
                "role": "tool",
                "tool_call_id": result.call_id,
                "name": result.name,
                "content": result.content,
            }
        )
    return new_messages


async def _run_retrieval_loop(
    messages: list[dict],
    tools: list,
    *,
    session: AsyncSession,
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
    llm_client: object,
) -> RetrievalLoopResult:
    """Run the bounded retrieval tool loop.

    Returns a RetrievalLoopResult after the loop exits. If the model emits text
    without tool calls on the first pass, that text can be reused as the final
    response to avoid a duplicate no-tool LLM call.
    """
    from backend.app.agents.provider_tools import NormalizedStreamEvent  # noqa: F401

    if not tools:
        return RetrievalLoopResult(messages=messages, tool_results=[])

    budget = settings.tutor_tool_call_budget
    all_results: list[NormalizedToolResult] = []
    dedup_cache: dict[tuple[str, str], NormalizedToolResult] = {}

    while budget > 0:
        events: list[NormalizedStreamEvent] = []
        async for event in llm_client.chat_stream_events(messages, tools=tools):  # type: ignore[attr-defined]
            events.append(event)

        tool_calls = [
            e.tool_call for e in events if e.kind == "tool_call" and e.tool_call is not None
        ]
        if not tool_calls:
            text = "".join(e.text or "" for e in events if e.kind == "text")
            thinking = "".join(e.text or "" for e in events if e.kind == "thinking")
            return RetrievalLoopResult(
                messages=messages,
                tool_results=all_results,
                text=text,
                thinking=thinking,
            )

        # Deduplicate: same name + same args -> reuse cached result but keep call_id.
        # Cached calls still count against the loop budget so repeated duplicate
        # requests cannot spin forever without adding new provider-visible turns.
        calls_for_round = tool_calls[:budget]
        budget -= len(calls_for_round)
        unique_calls: list[NormalizedToolCall] = []
        # Maps call_id -> cache_key for duplicates resolved this batch.
        dedup_this_batch: dict[str, tuple[str, str]] = {}
        cached_results: list[NormalizedToolResult] = []
        seen_keys: set[tuple[str, str]] = set()
        for tc in calls_for_round:
            cache_key = (tc.name, json.dumps(tc.arguments, sort_keys=True))
            if cache_key in dedup_cache:
                # Cross-iteration cache hit
                cached = dedup_cache[cache_key]
                cached_results.append(
                    NormalizedToolResult(
                        call_id=tc.call_id,
                        name=cached.name,
                        content=cached.content,
                        provider=cached.provider,
                        is_error=cached.is_error,
                        public_preview=cached.public_preview,
                    )
                )
            elif cache_key in seen_keys:
                # Intra-batch duplicate — back-fill after execution
                dedup_this_batch[tc.call_id] = cache_key
            else:
                seen_keys.add(cache_key)
                unique_calls.append(tc)

        # Execute all calls concurrently
        new_results = list(
            await asyncio.gather(
                *[
                    execute_retrieval_tool(
                        tc,
                        session=session,
                        workspace_id=workspace_id,
                        concept_id=concept_id,
                    )
                    for tc in unique_calls
                ]
            )
        )

        for tc, result in zip(unique_calls, new_results):
            cache_key = (tc.name, json.dumps(tc.arguments, sort_keys=True))
            dedup_cache[cache_key] = result
            all_results.append(result)

        # Back-fill intra-batch duplicates using the now-populated cache
        duplicate_results: list[NormalizedToolResult] = []
        for dup_call_id, cache_key in dedup_this_batch.items():
            cached = dedup_cache[cache_key]
            duplicate_results.append(
                NormalizedToolResult(
                    call_id=dup_call_id,
                    name=cached.name,
                    content=cached.content,
                    provider=cached.provider,
                    is_error=cached.is_error,
                    public_preview=cached.public_preview,
                )
            )
        all_results.extend(cached_results)
        all_results.extend(duplicate_results)

        round_results = [*new_results, *cached_results, *duplicate_results]
        messages = _append_tool_round(messages, calls_for_round, round_results)

        if any(_is_directed_retrieval_result(result) for result in round_results):
            break

    return RetrievalLoopResult(messages=messages, tool_results=all_results)


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
