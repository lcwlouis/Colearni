"""Artifact-builder sub-agent + detached/background generation (Phase 15a).

This module owns GENERATION of artifacts (the read/create/export foundation
lives in ``backend.app.services.artifacts``). It follows the orchestrator-worker
pattern with a small direct-provider adapter (NOT an agent framework):

- ``ArtifactBuilder`` is an injectable protocol; tests substitute a fake with no
  LLM calls. ``LLMArtifactBuilder`` is the production adapter over ``LLMClient``.
- Generation runs a BOUNDED retrieval loop (``settings.tutor_tool_call_budget``)
  that REUSES the existing retrieval tools and ``execute_retrieval_tool`` dispatch
  from ``conversations``. The revisions actually retrieved form the
  ``allowed_revision_ids`` set, so citations referencing unseen revisions are
  dropped by ``validate_artifact_payload``.
- Structured JSON output + EXACTLY ONE repair attempt, then fail (mirrors the
  primer/quiz repair).
- The BACKEND owns IDs, citations, persistence, and provenance/export gating; the
  model only returns a validated payload. Visibility is taken from the validated
  envelope but conservatively downgraded to ``local_only`` when zero citations
  remain (so a citation-less artifact can never be ``source_derived``).
- ``ArtifactGenerationManager`` runs detached, deduplicated background generation
  mirroring ``PrimerGenerationManager``: one in-flight generation per target
  ``(workspace, trail, concept_or_none, kind)``, cancel-safe, owning its own DB
  session, fenced across processes by a PostgreSQL advisory lock. A subscriber
  disconnect never aborts persistence.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import uuid
from hashlib import blake2b
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from sqlalchemy import select, text

from backend.app.agents.prompts import prompt_registry
from backend.app.agents.provider_tools import parse_text_tool_calls
from backend.app.agents.retrieval_tools import (
    GET_CONCEPT_PRIMER_TOOL,
    GET_CONCEPT_SOURCES_TOOL,
    GET_GRAPH_NEIGHBOURHOOD_TOOL,
    READ_DOCUMENT_SECTION_TOOL,
    SEARCH_SOURCES_TOOL,
)
from backend.app.models.artifact import Artifact
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.artifact import ArtifactEnvelopeOutput, ArtifactKind, ArtifactRead
from backend.app.services.artifacts import create_artifact, validate_artifact_payload
from backend.app.services.concept_primers import read_cached_primer
from backend.app.services.conversations import (
    _append_tool_round,
    execute_retrieval_tool,
    validate_concept_scope,
)
from backend.app.settings import settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from backend.app.agents.llm_client import LLMClient
    from backend.app.agents.prompts.registry import PromptRegistry
    from backend.app.agents.provider_tools import NormalizedStreamEvent, ProviderToolDefinition
    from backend.app.models.concept import ConceptNode

logger = logging.getLogger(__name__)

ARTIFACT_BUILDER_VERSION = 1
_RETRIEVAL_MAX_TOKENS = 1024
_GENERATION_MAX_TOKENS = 1400
# Extracts the revision id printed by the search_sources tool result formatter
# ("... | revision: <uuid>"). read_document_section ids are read from the call args.
_REVISION_RE = re.compile(r"revision:\s*([0-9a-fA-F-]{36})")

# Job key for the in-process dedupe registry. None concept_id => trail-level.
_ArtifactJobKey = tuple[uuid.UUID, uuid.UUID, "uuid.UUID | None", str]


class ArtifactGenerationError(Exception):
    pass


# ---------------------------------------------------------------------------
# Builder adapter (injectable)
# ---------------------------------------------------------------------------


@runtime_checkable
class ArtifactBuilder(Protocol):
    def retrieval_stream(
        self,
        messages: list[dict],
        *,
        tools: list[ProviderToolDefinition],
    ) -> AsyncIterator[NormalizedStreamEvent]: ...

    async def generate(self, messages: list[dict]) -> str: ...

    def generate_stream(self, messages: list[dict]) -> AsyncIterator[tuple[str, str]]: ...

    async def repair(self, raw: str, error: str) -> str:
        # Optional: return corrected artifact JSON for a validation failure.
        ...


class LLMArtifactBuilder:
    """Production builder: a thin direct-provider adapter over ``LLMClient``."""

    def __init__(self, client: LLMClient, registry: PromptRegistry = prompt_registry) -> None:
        self._client = client
        self._registry = registry

    async def retrieval_stream(
        self,
        messages: list[dict],
        *,
        tools: list[ProviderToolDefinition],
    ) -> AsyncIterator[NormalizedStreamEvent]:
        async for event in self._client.chat_stream_events(
            messages, tools=tools, max_tokens=_RETRIEVAL_MAX_TOKENS
        ):
            yield event

    async def generate(self, messages: list[dict]) -> str:
        return await self._client.chat(messages, temperature=0.3, max_tokens=_GENERATION_MAX_TOKENS)

    async def generate_stream(self, messages: list[dict]) -> AsyncIterator[tuple[str, str]]:
        async for kind, chunk in self._client.chat_stream_tagged(
            messages, temperature=0.3, max_tokens=_GENERATION_MAX_TOKENS
        ):
            if kind == "thinking":
                yield ("thinking", chunk)
            elif kind == "text":
                yield ("token", chunk)

    async def repair(self, raw: str, error: str) -> str:
        repair_prompt = (
            "The following artifact JSON failed validation. Return ONLY corrected "
            "JSON (no markdown fences, no explanation) matching the artifact "
            "envelope schema. Keep `artifact_version` = 1, the same `kind`, a "
            "non-empty `text_fallback`, and only citations whose source_revision_id "
            "you actually retrieved.\n\n"
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


async def build_artifact(
    session: AsyncSession,
    builder: ArtifactBuilder,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    kind: ArtifactKind,
    concept_id: uuid.UUID | None = None,
    force_new: bool = False,
) -> Artifact:
    """Build (or dedupe to) a single artifact synchronously and persist it.

    Single-flight: an advisory lock serializes concurrent PostgreSQL builders for
    the same target; after acquiring it we re-check for a recent artifact and
    return it instead of regenerating (unless ``force_new``).
    """
    trail, concept = await _validate_build_scope(
        session, workspace_id=workspace_id, trail_id=trail_id, concept_id=concept_id
    )
    scope_id = concept_id or trail_id
    await _lock_artifact_generation(session, scope_id=scope_id, kind=kind)

    if not force_new:
        existing = await _find_recent_artifact(
            session, workspace_id=workspace_id, trail_id=trail_id, concept_id=concept_id, kind=kind
        )
        if existing is not None:
            # Detach the loaded instance BEFORE rollback so the route can read its
            # (already-populated) columns without a lazy refresh on a rolled-back
            # async session (which would raise MissingGreenlet).
            session.expunge(existing)
            await session.rollback()
            return existing

    messages, allowed_revision_ids = await _gather_context(
        session,
        builder,
        trail=trail,
        concept=concept,
        workspace_id=workspace_id,
        concept_id=concept_id,
        kind=kind,
    )
    try:
        raw = await builder.generate(
            [*messages, {"role": "user", "content": _final_instruction(kind)}]
        )
        envelope = await _parse_or_repair_artifact(
            builder, raw, kind=kind, allowed_revision_ids=allowed_revision_ids
        )
    except ArtifactGenerationError:
        raise
    except Exception as exc:  # transport/provider failure -> uniform LLM error
        raise ArtifactGenerationError(str(exc)) from exc
    _enforce_visibility(envelope)
    return await create_artifact(
        session,
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=concept_id,
        envelope=envelope,
    )


async def stream_artifact(
    session: AsyncSession,
    builder: ArtifactBuilder,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    kind: ArtifactKind,
    concept_id: uuid.UUID | None = None,
    session_factory: async_sessionmaker[AsyncSession],
    manager: ArtifactGenerationManager | None = None,
) -> AsyncIterator[str]:
    """Yield SSE strings for artifact generation.

    Recent-artifact hit -> a single ``done`` event (no model call). Otherwise the
    actual generation runs in a DETACHED background task (see
    ``ArtifactGenerationManager``) that owns its OWN DB session and persists
    independently of this request. This generator only subscribes for a live
    preview, so a client disconnect never aborts generation/persist.
    """
    try:
        await _validate_build_scope(
            session, workspace_id=workspace_id, trail_id=trail_id, concept_id=concept_id
        )
    except LookupError as exc:
        yield _sse("error", {"type": "error", "code": "not_found", "message": str(exc)})
        return

    existing = await _find_recent_artifact(
        session, workspace_id=workspace_id, trail_id=trail_id, concept_id=concept_id, kind=kind
    )
    if existing is not None:
        yield _sse("done", {"type": "done", "artifact": _artifact_ref(existing)})
        return

    # Release the request-scoped connection before subscribing to the detached
    # job: generation no longer depends on this session.
    await session.rollback()

    manager = manager or artifact_generation_manager
    async for event in manager.stream(
        builder,
        session_factory,
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=concept_id,
        kind=kind,
    ):
        yield event


# ---------------------------------------------------------------------------
# Core generation (shared by sync + detached paths)
# ---------------------------------------------------------------------------


async def _produce_artifact_events(
    session: AsyncSession,
    builder: ArtifactBuilder,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID | None,
    kind: ArtifactKind,
) -> AsyncIterator[str]:
    """Core generation run inside the detached background task.

    Owns ``session`` (built by the manager from the sessionmaker) for its whole
    lifetime and commits the artifact via ``create_artifact``. Cross-process
    duplicate generation is fenced with a PostgreSQL advisory lock, and a recent
    artifact is re-checked after acquiring the lock so a build by another worker
    is returned without a model call.
    """
    try:
        trail, concept = await _validate_build_scope(
            session, workspace_id=workspace_id, trail_id=trail_id, concept_id=concept_id
        )
    except LookupError as exc:
        yield _sse("error", {"type": "error", "code": "not_found", "message": str(exc)})
        return

    scope_id = concept_id or trail_id
    await _lock_artifact_generation(session, scope_id=scope_id, kind=kind)
    existing = await _find_recent_artifact(
        session, workspace_id=workspace_id, trail_id=trail_id, concept_id=concept_id, kind=kind
    )
    if existing is not None:
        ref = _artifact_ref(existing)
        await session.rollback()
        yield _sse("done", {"type": "done", "artifact": ref})
        return

    yield _sse("status", {"type": "status", "status": "retrieving"})

    chunks: list[str] = []
    try:
        messages, allowed_revision_ids = await _gather_context(
            session,
            builder,
            trail=trail,
            concept=concept,
            workspace_id=workspace_id,
            concept_id=concept_id,
            kind=kind,
        )
        yield _sse("status", {"type": "status", "status": "generating"})
        final_messages = [*messages, {"role": "user", "content": _final_instruction(kind)}]
        async for chunk_kind, chunk in builder.generate_stream(final_messages):
            if chunk_kind == "thinking":
                # Reasoning preview only: never accumulated into the JSON buffer.
                yield _sse("thinking", {"type": "thinking", "content": chunk})
                continue
            if chunk_kind != "token":
                continue
            chunks.append(chunk)
            yield _sse("token", {"type": "token", "content": chunk})
        envelope = await _parse_or_repair_artifact(
            builder, "".join(chunks), kind=kind, allowed_revision_ids=allowed_revision_ids
        )
        _enforce_visibility(envelope)
        artifact = await create_artifact(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            envelope=envelope,
        )
    except Exception as exc:
        logger.exception(
            "detached artifact generation failed (workspace=%s trail=%s concept=%s kind=%s)",
            workspace_id,
            trail_id,
            concept_id,
            kind,
        )
        await session.rollback()
        yield _sse("error", {"type": "error", "code": "llm_error", "message": str(exc)})
        return

    yield _sse("done", {"type": "done", "artifact": _artifact_ref(artifact)})


async def _gather_context(
    session: AsyncSession,
    builder: ArtifactBuilder,
    *,
    trail: Trail,
    concept: ConceptNode | None,
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID | None,
    kind: ArtifactKind,
) -> tuple[list[dict], set[str]]:
    """Render the builder prompt and run the bounded retrieval loop.

    Returns the context-augmented messages plus the set of source_revision_ids
    actually retrieved (the allow-set for citation validation).
    """
    has_primer = concept is not None and read_cached_primer(concept) is not None
    tools = _select_builder_tools(concept_id=concept_id, has_primer=has_primer)
    messages = _build_messages(
        kind=kind, trail=trail, concept_title=concept.title if concept is not None else None
    )
    return await _run_builder_retrieval_loop(
        session,
        builder,
        messages,
        workspace_id=workspace_id,
        concept_id=concept_id,
        tools=tools,
    )


async def _run_builder_retrieval_loop(
    session: AsyncSession,
    builder: ArtifactBuilder,
    messages: list[dict],
    *,
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID | None,
    tools: list[ProviderToolDefinition],
) -> tuple[list[dict], set[str]]:
    """Bounded retrieval loop REUSING ``execute_retrieval_tool`` for dispatch.

    Obeys ``settings.tutor_tool_call_budget``. Tracks the source_revision_ids it
    actually retrieved so they form the citation allow-set.
    """
    allowed_revision_ids: set[str] = set()
    if not tools:
        return messages, allowed_revision_ids

    budget = settings.tutor_tool_call_budget
    while budget > 0:
        events = [event async for event in builder.retrieval_stream(messages, tools=tools)]
        tool_calls = [
            e.tool_call for e in events if e.kind == "tool_call" and e.tool_call is not None
        ]
        if not tool_calls:
            # Recover tool calls the model emitted as TEXT instead of native tool
            # calls (small/local models do this); otherwise the builder would
            # stop retrieving and produce a thinner, ungrounded artifact.
            text_out = "".join(e.text or "" for e in events if e.kind == "text")
            recovered = [c for c in parse_text_tool_calls(text_out, tools) if c.is_valid]
            if not recovered:
                break
            tool_calls = recovered

        calls = tool_calls[:budget]
        budget -= len(calls)
        # Execute SEQUENTIALLY: every call shares this one AsyncSession, and a
        # single asyncpg connection cannot run concurrent operations. Dispatching
        # these with asyncio.gather corrupts the in-flight transaction
        # (InFailedSQLTransactionError) the moment the model emits >1 tool call,
        # which then aborts the later create_artifact commit. Retrieval is
        # read-only and the budget is tiny, so the latency cost is negligible.
        results = []
        for tc in calls:
            results.append(
                await execute_retrieval_tool(
                    tc,
                    session=session,
                    workspace_id=workspace_id,
                    # Trail-level builds (concept_id is None) only offer
                    # workspace-wide tools (search/read), so a None scope is
                    # never used by a concept-scoped tool.
                    concept_id=concept_id,  # type: ignore[arg-type]
                )
            )

        for tc, result in zip(calls, results):
            allowed_revision_ids |= _extract_revision_ids(result.content)
            # Only authorize a directly-read revision id when the read actually
            # SUCCEEDED. A failed/out-of-workspace read returns is_error=True; we
            # must not let the model launder an arbitrary revision id (and then
            # attach a fabricated quote) into the citation allow-set.
            if tc.name == "read_document_section" and tc.is_valid and not result.is_error:
                revision_id = tc.arguments.get("source_revision_id")
                if revision_id:
                    allowed_revision_ids.add(str(revision_id))

        messages = _append_tool_round(messages, calls, results)

    return messages, allowed_revision_ids


# ---------------------------------------------------------------------------
# Detached generation manager (mirrors PrimerGenerationManager)
# ---------------------------------------------------------------------------


class _ArtifactJob:
    """A single in-flight artifact generation, shared by all current subscribers."""

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


class ArtifactGenerationManager:
    """Owns detached, deduplicated artifact generation tasks.

    One in-flight generation per ``(workspace, trail, concept_or_none, kind)`` at
    most (in-process dedup): near-simultaneous opens share the same background
    task and therefore the same single model run. Tasks are created with
    ``asyncio.create_task`` and are NOT tied to the request that started them, so
    a client disconnect only cancels that client's subscription; the generation
    runs to completion and persists. The cross-process boundary is the advisory
    lock inside :func:`_produce_artifact_events`.
    """

    def __init__(self) -> None:
        self._jobs: dict[_ArtifactJobKey, _ArtifactJob] = {}
        self._lock = asyncio.Lock()

    async def stream(
        self,
        builder: ArtifactBuilder,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        workspace_id: uuid.UUID,
        trail_id: uuid.UUID,
        concept_id: uuid.UUID | None,
        kind: ArtifactKind,
    ) -> AsyncIterator[str]:
        key = (workspace_id, trail_id, concept_id, kind)
        job = await self._ensure_job(
            key,
            builder,
            session_factory,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
            kind=kind,
        )
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        # Snapshot already-emitted events and subscribe atomically so no event
        # is lost or duplicated between the replay and going live.
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
            # Disconnect path: drop this subscriber but leave the job running.
            async with job.lock:
                job.subscribers.discard(queue)

    async def _ensure_job(
        self,
        key: _ArtifactJobKey,
        builder: ArtifactBuilder,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        workspace_id: uuid.UUID,
        trail_id: uuid.UUID,
        concept_id: uuid.UUID | None,
        kind: ArtifactKind,
    ) -> _ArtifactJob:
        async with self._lock:
            existing = self._jobs.get(key)
            if existing is not None and not existing.finished:
                return existing
            job = _ArtifactJob()
            self._jobs[key] = job
            job.task = asyncio.create_task(
                self._run(
                    key,
                    job,
                    builder,
                    session_factory,
                    workspace_id=workspace_id,
                    trail_id=trail_id,
                    concept_id=concept_id,
                    kind=kind,
                )
            )
            return job

    async def _run(
        self,
        key: _ArtifactJobKey,
        job: _ArtifactJob,
        builder: ArtifactBuilder,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        workspace_id: uuid.UUID,
        trail_id: uuid.UUID,
        concept_id: uuid.UUID | None,
        kind: ArtifactKind,
    ) -> None:
        try:
            async with session_factory() as session:
                async for event in _produce_artifact_events(
                    session,
                    builder,
                    workspace_id=workspace_id,
                    trail_id=trail_id,
                    concept_id=concept_id,
                    kind=kind,
                ):
                    await job.publish(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # background safety net: never crash the loop.
            logger.exception("detached artifact generation failed for %s", key)
            await job.publish(
                _sse("error", {"type": "error", "code": "llm_error", "message": str(exc)})
            )
        finally:
            await job.finish()
            async with self._lock:
                if self._jobs.get(key) is job:
                    del self._jobs[key]

    async def shutdown(self) -> None:
        """Cancel and await any outstanding generations (lifespan teardown)."""
        async with self._lock:
            tasks = [job.task for job in self._jobs.values() if job.task is not None]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    async def drain(self) -> None:
        """Await all outstanding generations to completion (tests / graceful flush)."""
        while True:
            async with self._lock:
                tasks = [job.task for job in self._jobs.values() if job.task is not None]
            if not tasks:
                return
            await asyncio.gather(*tasks, return_exceptions=True)


# Process-wide registry of in-flight artifact generations. Instantiated at import
# (no startup hook needed); main.py's lifespan owns its clean shutdown. Replace
# with a shared external worker/queue if artifact generation moves off-process.
artifact_generation_manager = ArtifactGenerationManager()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _validate_build_scope(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID | None,
) -> tuple[Trail, ConceptNode | None]:
    """Validate workspace -> trail (-> concept) scope. Returns (trail, concept|None)."""
    if concept_id is not None:
        return await validate_concept_scope(
            session, workspace_id=workspace_id, trail_id=trail_id, concept_id=concept_id
        )
    if await session.get(Workspace, workspace_id) is None:
        raise LookupError(f"Workspace {workspace_id} not found")
    trail = await session.scalar(
        select(Trail).where(Trail.id == trail_id, Trail.workspace_id == workspace_id)
    )
    if trail is None:
        raise LookupError(f"Trail {trail_id} not found")
    return trail, None


def _select_builder_tools(
    *,
    concept_id: uuid.UUID | None,
    has_primer: bool,
) -> list[ProviderToolDefinition]:
    """Retrieval tool set for the builder.

    Workspace-wide tools (search/read) are always offered. Concept-scoped tools
    (concept sources, graph neighbourhood, primer) are only offered for a
    concept-level build so a ``None`` scope is never handed to them.
    """
    tools: list[ProviderToolDefinition] = [SEARCH_SOURCES_TOOL, READ_DOCUMENT_SECTION_TOOL]
    if concept_id is not None:
        tools.append(GET_CONCEPT_SOURCES_TOOL)
        tools.append(GET_GRAPH_NEIGHBOURHOOD_TOOL)
        if has_primer:
            tools.append(GET_CONCEPT_PRIMER_TOOL)
    return tools


def _build_messages(
    *,
    kind: ArtifactKind,
    trail: Trail,
    concept_title: str | None,
) -> list[dict]:
    system = prompt_registry.render(
        "artifact_builder",
        {
            "kind": kind,
            "topic": trail.topic,
            "goal": trail.goal,
            "concept_title": concept_title or "(whole trail)",
        },
        version=ARTIFACT_BUILDER_VERSION,
    )
    user = (
        f"Build one {kind} artifact for "
        f"{concept_title or 'this trail'}. Retrieve context first, then output the JSON."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _final_instruction(kind: ArtifactKind) -> str:
    return (
        f"Now output the final {kind} artifact as a SINGLE JSON object matching the "
        "schema. Return ONLY JSON, no markdown fences, no commentary. Every citation's "
        "source_revision_id MUST be one you actually retrieved above."
    )


def _extract_revision_ids(content: str) -> set[str]:
    return set(_REVISION_RE.findall(content or ""))


def _parse_artifact_json(
    raw: str,
    *,
    kind: ArtifactKind,
    allowed_revision_ids: set[str] | None,
) -> ArtifactEnvelopeOutput:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ArtifactGenerationError(f"Artifact generation returned invalid JSON: {exc}") from exc
    try:
        envelope = validate_artifact_payload(data, allowed_revision_ids=allowed_revision_ids)
    except Exception as exc:
        raise ArtifactGenerationError(f"Artifact failed validation: {exc}") from exc
    if envelope.kind != kind:
        raise ArtifactGenerationError(
            f"Artifact kind mismatch: requested {kind}, model produced {envelope.kind}"
        )
    return envelope


async def _parse_or_repair_artifact(
    builder: ArtifactBuilder,
    raw: str,
    *,
    kind: ArtifactKind,
    allowed_revision_ids: set[str] | None,
) -> ArtifactEnvelopeOutput:
    """Parse artifact JSON, falling back to EXACTLY ONE builder repair attempt."""
    try:
        return _parse_artifact_json(raw, kind=kind, allowed_revision_ids=allowed_revision_ids)
    except ArtifactGenerationError as exc:
        repair = getattr(builder, "repair", None)
        if repair is None:
            raise
        repaired = await repair(raw, str(exc))
        try:
            return _parse_artifact_json(
                repaired, kind=kind, allowed_revision_ids=allowed_revision_ids
            )
        except ArtifactGenerationError as repair_exc:
            raise ArtifactGenerationError(
                f"Artifact failed validation after repair: {repair_exc}"
            ) from repair_exc


def _enforce_visibility(envelope: ArtifactEnvelopeOutput) -> ArtifactEnvelopeOutput:
    """Conservatively downgrade to local_only when no citations remain.

    Citations referencing non-retrieved revisions are dropped during validation,
    so a citation-less artifact can never be source_derived.
    """
    if envelope.provenance.visibility == "source_derived" and not envelope.provenance.citations:
        envelope.provenance.visibility = "local_only"
    return envelope


async def _find_recent_artifact(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID | None,
    kind: ArtifactKind,
) -> Artifact | None:
    """Most recent artifact for the same target + kind (single-flight dedupe)."""
    stmt = select(Artifact).where(
        Artifact.workspace_id == workspace_id,
        Artifact.trail_id == trail_id,
        Artifact.artifact_type == kind,
    )
    stmt = stmt.where(
        Artifact.concept_id.is_(None) if concept_id is None else Artifact.concept_id == concept_id
    )
    stmt = stmt.order_by(Artifact.created_at.desc()).limit(1)
    return await session.scalar(stmt)


def _artifact_ref(artifact: Artifact) -> dict:
    """Serialize a persisted artifact as the SSE/done reference payload."""
    return ArtifactRead.model_validate(artifact).model_dump(mode="json")


async def _lock_artifact_generation(
    session: AsyncSession,
    *,
    scope_id: uuid.UUID,
    kind: ArtifactKind,
) -> None:
    """Serialize PostgreSQL artifact generation so duplicate workers reuse one call."""
    connection = await session.connection()
    if connection.dialect.name != "postgresql":
        return
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": _artifact_lock_key(scope_id, kind)},
    )


def _artifact_lock_key(scope_id: uuid.UUID, kind: ArtifactKind) -> int:
    digest = blake2b(f"artifact:{scope_id}:{kind}".encode("ascii"), digest_size=8).digest()
    return int.from_bytes(digest, "big") & 0x7FFFFFFFFFFFFFFF


def _sse(event_type: str, data: dict) -> str:
    """Format a single Server-Sent Event string."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
