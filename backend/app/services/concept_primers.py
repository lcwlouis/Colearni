"""Concept primer service: separate LLM pass that generates and caches a short
orientation overview + key-terms glossary for a single concept.

The primer is abstract, concept-level orientation content (NOT source-derived).
It is generated in its own pass after graph generation — never inlined into
trail generation — to keep graph JSON lean and reliable on smaller models.

The primer is graph-aware: it is anchored to the concept's actual graph
neighbourhood (1-2 layers out) and its mastery checks so the model favours key
terms that exist nearby instead of inventing unrelated topics.

The PrimerGenerator protocol is injectable; tests substitute a fake without any
LLM calls. Generation is idempotent: a cached primer is returned without calling
the model unless force_new is set.
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
from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.schemas.concept import ConceptPrimerOutput, ConceptPrimerRead
from backend.app.services.conversations import validate_concept_scope
from backend.app.services.retrieval import get_graph_neighbourhood

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from backend.app.agents.llm_client import LLMClient
    from backend.app.agents.prompts.registry import PromptRegistry
    from backend.app.models.trail import Trail

logger = logging.getLogger(__name__)

PRIMER_VERSION = 2
PRIMER_METADATA_KEY = "primer"
_PRIMER_MAX_TOKENS = 700
# Keep the neighbour context token-bounded: titles only, capped overall.
_NEARBY_TITLE_CAP = 20
# Keys whose values are lists of neighbour titles rendered into the prompt.
_NEIGHBOUR_KEYS = (
    "prerequisites",
    "containing_nodes",
    "contained_nodes",
    "related",
    "application_nodes",
)


class PrimerGenerationError(Exception):
    pass


@runtime_checkable
class PrimerGenerator(Protocol):
    async def generate(
        self,
        *,
        concept: ConceptNode,
        trail: Trail,
        neighbour_context: dict[str, list[str]],
    ) -> ConceptPrimerOutput: ...

    def generate_stream(
        self,
        *,
        concept: ConceptNode,
        trail: Trail,
        neighbour_context: dict[str, list[str]],
    ) -> AsyncIterator[tuple[str, str]]: ...


class LLMPrimerGenerator:
    def __init__(
        self,
        client: LLMClient,
        registry: PromptRegistry = prompt_registry,
    ) -> None:
        self._client = client
        self._registry = registry

    def _render_prompt(
        self,
        *,
        concept: ConceptNode,
        trail: Trail,
        neighbour_context: dict[str, list[str]],
    ) -> str:
        variables = {
            "topic": trail.topic,
            "goal": trail.goal,
            "concept_title": concept.title,
            "concept_level": concept.concept_level,
            "bloom_target": concept.bloom_level,
            "mastery_check_labels": json.dumps(concept.mastery_check_labels, indent=2),
        }
        for key in (*_NEIGHBOUR_KEYS, "nearby"):
            variables[key] = _format_titles(neighbour_context.get(key))
        return self._registry.render("concept_primer", variables, version=PRIMER_VERSION)

    async def generate(
        self,
        *,
        concept: ConceptNode,
        trail: Trail,
        neighbour_context: dict[str, list[str]],
    ) -> ConceptPrimerOutput:
        prompt = self._render_prompt(
            concept=concept, trail=trail, neighbour_context=neighbour_context
        )
        raw = await self._client.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=_PRIMER_MAX_TOKENS,
        )
        return _parse_primer_output(raw)

    async def generate_stream(
        self,
        *,
        concept: ConceptNode,
        trail: Trail,
        neighbour_context: dict[str, list[str]],
    ) -> AsyncIterator[tuple[str, str]]:
        """Stream the raw model output as tagged (kind, chunk) tuples.

        Both channels are surfaced so callers can show a live preview of the
        reasoning while the model thinks: "thinking" chunks are yielded as
        ("thinking", chunk) and output text as ("token", chunk). Only the
        "token" stream is accumulated and parsed with _parse_primer_output;
        reasoning is cosmetic and never fed into the JSON parser.
        """
        prompt = self._render_prompt(
            concept=concept, trail=trail, neighbour_context=neighbour_context
        )
        async for kind, chunk in self._client.chat_stream_tagged(
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=_PRIMER_MAX_TOKENS,
        ):
            if kind == "thinking":
                yield ("thinking", chunk)
            elif kind == "text":
                yield ("token", chunk)


async def generate_concept_primer(
    session: AsyncSession,
    generator: PrimerGenerator,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    force_new: bool = False,
) -> ConceptPrimerRead:
    """Generate and cache a primer for one concept.

    Idempotent: if a primer is already cached on the concept it is returned
    WITHOUT calling the model, unless force_new is True. The cache lives in
    ConceptNode.metadata_json under PRIMER_METADATA_KEY to avoid a migration.

    Designed so a future bounded background pass can loop over concepts and call
    this per concept; the loop itself is intentionally not built here.
    """
    trail, concept = await validate_concept_scope(
        session,
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=concept_id,
    )

    if not force_new:
        cached = read_cached_primer(concept)
        if cached is not None:
            return cached

    neighbour_context = await _load_neighbour_context(session, trail=trail, concept=concept)
    output = await generator.generate(
        concept=concept, trail=trail, neighbour_context=neighbour_context
    )
    return await _cache_primer(session, concept, output)


async def stream_concept_primer(
    session: AsyncSession,
    generator: PrimerGenerator,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession],
    manager: PrimerGenerationManager | None = None,
) -> AsyncIterator[str]:
    """Yield SSE strings for primer generation (see docs/API for the contract).

    Cache hit -> a single `done` event (no model call). Otherwise the actual
    generation runs in a DETACHED background task (see PrimerGenerationManager)
    that owns its OWN DB session built from ``session_factory`` and commits the
    cached primer independently of this request. This generator only subscribes
    to that background job's event stream for a live preview, so a client
    disconnect (which cancels THIS generator) never aborts generation/persist.

    Background event order on a miss: `status` (preparing) -> zero or more
    `thinking`/`token` events interleaved (a cosmetic live preview: reasoning
    tokens stream first on reasoning models, output text follows) -> on success
    persist + `done`, on failure `error`. Only `token` content is accumulated
    and parsed; `thinking` content is preview-only and never enters the JSON
    buffer.
    """
    try:
        _trail, concept = await validate_concept_scope(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
        )
    except LookupError as exc:
        yield _sse("error", {"type": "error", "code": "not_found", "message": str(exc)})
        return

    cached = read_cached_primer(concept)
    if cached is not None:
        yield _sse("done", {"type": "done", "primer": cached.model_dump(mode="json")})
        return

    # Release the request-scoped connection before subscribing to the detached
    # job: generation no longer depends on this session, and we must not hold a
    # request connection open for the whole stream. (Past this point we use the
    # input concept_id, never the now-expired `concept` instance.)
    await session.rollback()

    manager = manager or primer_generation_manager
    async for event in manager.stream(
        generator,
        session_factory,
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=concept_id,
    ):
        yield event


async def _produce_primer_events(
    session: AsyncSession,
    generator: PrimerGenerator,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID,
) -> AsyncIterator[str]:
    """Core generation run inside the detached background task.

    Owns ``session`` (built by the manager from the sessionmaker) for its entire
    lifetime and commits the cached primer via _cache_primer. Cross-process
    duplicate generation is fenced with a PostgreSQL advisory lock (mirroring
    quiz drafts), and the cache is re-checked after acquiring the lock so a
    primer generated by another worker is returned without a model call.
    """
    try:
        trail, concept = await validate_concept_scope(
            session,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
        )
    except LookupError as exc:
        yield _sse("error", {"type": "error", "code": "not_found", "message": str(exc)})
        return

    await _lock_primer_generation(session, concept_id=concept.id)
    await session.refresh(concept)
    cached = read_cached_primer(concept)
    if cached is not None:
        await session.rollback()
        yield _sse("done", {"type": "done", "primer": cached.model_dump(mode="json")})
        return

    neighbour_context = await _load_neighbour_context(session, trail=trail, concept=concept)
    yield _sse("status", {"type": "status", "status": "preparing"})

    chunks: list[str] = []
    try:
        async for kind, chunk in generator.generate_stream(
            concept=concept, trail=trail, neighbour_context=neighbour_context
        ):
            if kind == "thinking":
                # Reasoning preview only: never accumulated into the JSON buffer.
                yield _sse("thinking", {"type": "thinking", "content": chunk})
                continue
            if kind != "token":
                continue
            chunks.append(chunk)
            yield _sse("token", {"type": "token", "content": chunk})
        output = _parse_primer_output("".join(chunks))
        primer = await _cache_primer(session, concept, output)
    except Exception as exc:
        await session.rollback()
        yield _sse("error", {"type": "error", "code": "llm_error", "message": str(exc)})
        return

    yield _sse("done", {"type": "done", "primer": primer.model_dump(mode="json")})


class _PrimerJob:
    """A single in-flight primer generation, shared by all current subscribers.

    The background task feeds SSE strings via :meth:`publish`; every event is
    buffered so a late subscriber can replay what it missed, and fanned out to
    each live subscriber queue. :meth:`finish` closes every subscriber with a
    ``None`` sentinel.
    """

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


class PrimerGenerationManager:
    """Owns detached, deduplicated primer generation tasks.

    One in-flight generation per concept_id at most (in-process dedup): two
    near-simultaneous opens share the same background task and therefore the
    same single model call. Tasks are created with ``asyncio.create_task`` and
    are NOT tied to the request that started them, so a client disconnect only
    cancels that client's subscription; the generation runs to completion and
    persists. The cross-process boundary is the advisory lock inside
    :func:`_produce_primer_events`.
    """

    def __init__(self) -> None:
        self._jobs: dict[uuid.UUID, _PrimerJob] = {}
        self._lock = asyncio.Lock()

    async def stream(
        self,
        generator: PrimerGenerator,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        workspace_id: uuid.UUID,
        trail_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> AsyncIterator[str]:
        job = await self._ensure_job(
            generator,
            session_factory,
            workspace_id=workspace_id,
            trail_id=trail_id,
            concept_id=concept_id,
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
        generator: PrimerGenerator,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        workspace_id: uuid.UUID,
        trail_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> _PrimerJob:
        async with self._lock:
            existing = self._jobs.get(concept_id)
            if existing is not None and not existing.finished:
                return existing
            job = _PrimerJob()
            self._jobs[concept_id] = job
            job.task = asyncio.create_task(
                self._run(
                    job,
                    generator,
                    session_factory,
                    workspace_id=workspace_id,
                    trail_id=trail_id,
                    concept_id=concept_id,
                )
            )
            return job

    async def _run(
        self,
        job: _PrimerJob,
        generator: PrimerGenerator,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        workspace_id: uuid.UUID,
        trail_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> None:
        try:
            async with session_factory() as session:
                async for event in _produce_primer_events(
                    session,
                    generator,
                    workspace_id=workspace_id,
                    trail_id=trail_id,
                    concept_id=concept_id,
                ):
                    await job.publish(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # background safety net: never crash the loop.
            logger.exception("detached primer generation failed for concept %s", concept_id)
            await job.publish(
                _sse("error", {"type": "error", "code": "llm_error", "message": str(exc)})
            )
        finally:
            await job.finish()
            async with self._lock:
                if self._jobs.get(concept_id) is job:
                    del self._jobs[concept_id]

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


# Process-wide registry of in-flight primer generations. Instantiated at import
# (no startup hook needed); main.py's lifespan owns its clean shutdown. Replace
# with a shared external worker/queue if primer generation moves off-process.
primer_generation_manager = PrimerGenerationManager()


async def _lock_primer_generation(
    session: AsyncSession,
    *,
    concept_id: uuid.UUID,
) -> None:
    """Serialize PostgreSQL primer generation so duplicate workers reuse one call."""
    connection = await session.connection()
    if connection.dialect.name != "postgresql":
        return
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": _primer_lock_key(concept_id)},
    )


def _primer_lock_key(concept_id: uuid.UUID) -> int:
    digest = blake2b(f"primer:{concept_id}".encode("ascii"), digest_size=8).digest()
    return int.from_bytes(digest, "big") & 0x7FFFFFFFFFFFFFFF


def read_cached_primer(concept: ConceptNode) -> ConceptPrimerRead | None:
    """Return the cached primer for a concept, or None when absent/unreadable.

    Tolerates primers cached before sample_questions existed (the field defaults
    to an empty list), so older caches are not forced to regenerate.
    """
    raw = (concept.metadata_json or {}).get(PRIMER_METADATA_KEY)
    if not raw:
        return None
    try:
        return ConceptPrimerRead.model_validate(raw)
    except Exception:
        return None


async def _cache_primer(
    session: AsyncSession,
    concept: ConceptNode,
    output: ConceptPrimerOutput,
) -> ConceptPrimerRead:
    primer = ConceptPrimerRead(
        overview=output.overview,
        key_terms=output.key_terms,
        sample_questions=output.sample_questions,
        version=PRIMER_VERSION,
    )
    # Reassign a new dict so SQLAlchemy detects the JSON column change.
    metadata = dict(concept.metadata_json or {})
    metadata[PRIMER_METADATA_KEY] = primer.model_dump(mode="json")
    concept.metadata_json = metadata
    await session.commit()
    return primer


async def _load_neighbour_context(
    session: AsyncSession,
    *,
    trail: Trail,
    concept: ConceptNode,
) -> dict[str, list[str]]:
    """Load the concept's graph neighbourhood 1-2 layers deep as plain titles.

    Layer 1 comes straight from get_graph_neighbourhood. Layer 2 expands once
    more from each direct neighbour into a flat `nearby` list, deduped by id,
    excluding the concept and its direct neighbours, capped at _NEARBY_TITLE_CAP
    to stay token-bounded.
    """
    all_nodes = list(
        await session.scalars(select(ConceptNode).where(ConceptNode.trail_id == trail.id))
    )
    edges = list(await session.scalars(select(ConceptEdge).where(ConceptEdge.trail_id == trail.id)))

    neighbourhood = get_graph_neighbourhood(concept=concept, all_nodes=all_nodes, edges=edges)
    context: dict[str, list[str]] = {
        key: [node.title for node in neighbourhood[key]] for key in _NEIGHBOUR_KEYS
    }

    # Layer 2: expand from each direct neighbour, excluding already-known nodes.
    excluded_ids: set[uuid.UUID] = {concept.id}
    direct_neighbours: list[ConceptNode] = []
    for key in _NEIGHBOUR_KEYS:
        for node in neighbourhood[key]:
            excluded_ids.add(node.id)
            direct_neighbours.append(node)

    nearby: list[str] = []
    nearby_ids: set[uuid.UUID] = set()
    for neighbour in direct_neighbours:
        if len(nearby) >= _NEARBY_TITLE_CAP:
            break
        second = get_graph_neighbourhood(concept=neighbour, all_nodes=all_nodes, edges=edges)
        for key in _NEIGHBOUR_KEYS:
            for node in second[key]:
                if node.id in excluded_ids or node.id in nearby_ids:
                    continue
                nearby_ids.add(node.id)
                nearby.append(node.title)
                if len(nearby) >= _NEARBY_TITLE_CAP:
                    break
            if len(nearby) >= _NEARBY_TITLE_CAP:
                break

    context["nearby"] = nearby
    return context


def _format_titles(titles: list[str] | None) -> str:
    if not titles:
        return "(none)"
    return ", ".join(titles)


def _sse(event_type: str, data: dict) -> str:
    """Format a single Server-Sent Event string."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def _parse_primer_output(raw: str) -> ConceptPrimerOutput:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise PrimerGenerationError(f"Primer generation returned invalid JSON: {exc}") from exc
    try:
        return ConceptPrimerOutput.model_validate(data)
    except Exception as exc:
        raise PrimerGenerationError(f"Primer generation failed validation: {exc}") from exc
