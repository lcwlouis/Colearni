import asyncio
import json

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.models.base import Base
from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.schemas.concept import ConceptPrimerOutput
from backend.app.services.concept_primers import (
    LLMPrimerGenerator,
    PrimerGenerationError,
    PrimerGenerationManager,
    generate_concept_primer,
    read_cached_primer,
    stream_concept_primer,
)
from backend.app.services.graph_view import get_concept_detail


class FakeLLMClient:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls: list[list[dict]] = []

    async def chat(self, messages: list[dict], **_: object) -> str:
        self.calls.append(messages)
        return self.responses.pop(0)


class FakePrimerGenerator:
    def __init__(self, output: ConceptPrimerOutput | None = None):
        self.output = output or ConceptPrimerOutput(
            overview="Derivatives measure how a quantity changes.",
            key_terms=[
                {"term": "Slope", "definition": "The rate of change at a point."},
                {"term": "Limit", "definition": "The value a function approaches."},
                {"term": "Tangent", "definition": "A line touching a curve at one point."},
            ],
            sample_questions=[
                "Walk me through what a derivative is.",
                "Give me one hint to start.",
                "Check my understanding of slope.",
            ],
        )
        self.calls: list[tuple[str, str]] = []
        self.neighbour_contexts: list[dict] = []

    async def generate(
        self, *, concept: ConceptNode, trail: Trail, neighbour_context: dict
    ) -> ConceptPrimerOutput:
        self.calls.append((concept.title, trail.topic))
        self.neighbour_contexts.append(neighbour_context)
        return self.output

    async def generate_stream(self, *, concept: ConceptNode, trail: Trail, neighbour_context: dict):
        self.calls.append((concept.title, trail.topic))
        self.neighbour_contexts.append(neighbour_context)
        payload = json.dumps(self.output.model_dump(mode="json"))
        # Reasoning streams first on reasoning models; it must never enter the
        # parsed JSON buffer.
        yield ("thinking", "Let me orient the learner around ")
        yield ("thinking", "the key terms first.")
        # Emit output in two chunks to exercise accumulation.
        mid = len(payload) // 2
        yield ("token", payload[:mid])
        yield ("token", payload[mid:])


@pytest.fixture
async def session_factory(tmp_path):
    # File-backed SQLite: the detached background task opens its OWN connection
    # concurrently with the request session, which a single shared in-memory
    # connection (StaticPool) cannot serialize. Mirrors Postgres' separate pool
    # connections in production.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'primer.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    yield maker
    await engine.dispose()


@pytest.fixture
async def session(session_factory):
    async with session_factory() as session:
        yield session


async def _seed_concept(session):
    workspace = Workspace(name="Primer Workspace")
    session.add(workspace)
    await session.flush()
    trail = Trail(
        workspace_id=workspace.id,
        title="Calculus",
        topic="Calculus",
        goal="Understand derivatives",
        target_depth="apply",
    )
    session.add(trail)
    await session.flush()
    concept = ConceptNode(
        trail_id=trail.id,
        slug="derivatives",
        title="Derivatives",
        node_type="concept",
        concept_level="topic",
        difficulty="beginner",
        bloom_level="apply",
        mastery_check_labels=["explain_derivative", "apply_derivative"],
        metadata_json={},
    )
    session.add(concept)
    await session.commit()
    return workspace, trail, concept


async def _seed_neighbour(session, trail, *, slug, title, relation, concept):
    """Add a neighbour node + an edge to `concept` and return the new node."""
    node = ConceptNode(
        trail_id=trail.id,
        slug=slug,
        title=title,
        node_type="concept",
        concept_level="topic",
        difficulty="beginner",
        bloom_level="understand",
        mastery_check_labels=[f"explain_{slug}"],
        metadata_json={},
    )
    session.add(node)
    await session.flush()
    if relation == "prerequisite":
        edge = ConceptEdge(
            trail_id=trail.id,
            source_node_id=node.id,
            target_node_id=concept.id,
            relation_type="prerequisite",
        )
    else:
        edge = ConceptEdge(
            trail_id=trail.id,
            source_node_id=concept.id,
            target_node_id=node.id,
            relation_type=relation,
        )
    session.add(edge)
    await session.commit()
    return node


async def test_generate_primer_returns_overview_and_key_terms(session):
    workspace, trail, concept = await _seed_concept(session)
    generator = FakePrimerGenerator()

    primer = await generate_concept_primer(
        session,
        generator,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )

    assert primer.overview.startswith("Derivatives")
    assert len(primer.key_terms) == 3
    assert [term.term for term in primer.key_terms] == ["Slope", "Limit", "Tangent"]
    assert len(primer.sample_questions) == 3
    assert primer.version == 2
    assert generator.calls == [("Derivatives", "Calculus")]
    # The generator is handed graph neighbour context (empty here: no edges seeded).
    assert generator.neighbour_contexts[0].keys() >= {
        "prerequisites",
        "related",
        "nearby",
    }


async def test_generate_primer_is_cached_and_idempotent(session):
    workspace, trail, concept = await _seed_concept(session)
    generator = FakePrimerGenerator()

    first = await generate_concept_primer(
        session,
        generator,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )
    second = await generate_concept_primer(
        session,
        generator,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )

    assert second == first
    # The model is only invoked once; the second call is served from the cache.
    assert generator.calls == [("Derivatives", "Calculus")]
    await session.refresh(concept)
    assert read_cached_primer(concept) == first


async def test_force_new_regenerates_primer(session):
    workspace, trail, concept = await _seed_concept(session)
    generator = FakePrimerGenerator()

    await generate_concept_primer(
        session,
        generator,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )
    await generate_concept_primer(
        session,
        generator,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        force_new=True,
    )

    assert generator.calls == [
        ("Derivatives", "Calculus"),
        ("Derivatives", "Calculus"),
    ]


async def test_concept_detail_includes_primer_when_present(session):
    workspace, trail, concept = await _seed_concept(session)
    generator = FakePrimerGenerator()

    await generate_concept_primer(
        session,
        generator,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )

    detail = await get_concept_detail(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )

    assert detail["primer"] is not None
    assert detail["primer"].overview.startswith("Derivatives")
    assert len(detail["primer"].key_terms) == 3


async def test_concept_detail_omits_primer_when_absent(session):
    workspace, trail, concept = await _seed_concept(session)

    detail = await get_concept_detail(
        session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )

    assert detail["primer"] is None


async def test_llm_primer_generator_renders_prompt_and_parses_output(session):
    _, trail, concept = await _seed_concept(session)
    client = FakeLLMClient(
        [
            """
            ```json
            {
              "overview": "Derivatives describe instantaneous change.",
              "key_terms": [
                {"term": "Slope", "definition": "Rate of change at a point."},
                {"term": "Limit", "definition": "Value a function approaches."},
                {"term": "Tangent", "definition": "Line touching a curve once."}
              ],
              "sample_questions": [
                "Walk me through what a derivative is.",
                "Give me a hint to start.",
                "Check my understanding of slope."
              ]
            }
            ```
            """
        ]
    )
    generator = LLMPrimerGenerator(client=client)

    output = await generator.generate(concept=concept, trail=trail, neighbour_context={})

    assert output.overview == "Derivatives describe instantaneous change."
    assert len(output.key_terms) == 3
    assert output.sample_questions == [
        "Walk me through what a derivative is.",
        "Give me a hint to start.",
        "Check my understanding of slope.",
    ]
    prompt = client.calls[0][0]["content"]
    assert "Derivatives" in prompt
    assert "Calculus" in prompt
    assert "explain_derivative" in prompt
    # The prompt nudges key terms toward contained and related neighbours.
    assert "contained" in prompt
    assert "related" in prompt
    assert "most useful for orienting a learner" in prompt


async def test_llm_primer_generator_rejects_invalid_json(session):
    _, trail, concept = await _seed_concept(session)
    generator = LLMPrimerGenerator(client=FakeLLMClient(["not json"]))

    with pytest.raises(PrimerGenerationError):
        await generator.generate(concept=concept, trail=trail, neighbour_context={})


async def test_llm_primer_generator_rejects_too_few_key_terms(session):
    _, trail, concept = await _seed_concept(session)
    client = FakeLLMClient(
        [
            """
            {
              "overview": "Too short.",
              "key_terms": [
                {"term": "Slope", "definition": "Rate of change."}
              ]
            }
            """
        ]
    )
    generator = LLMPrimerGenerator(client=client)

    with pytest.raises(PrimerGenerationError):
        await generator.generate(concept=concept, trail=trail, neighbour_context={})


async def test_generate_primer_passes_graph_neighbours_to_generator(session):
    workspace, trail, concept = await _seed_concept(session)
    await _seed_neighbour(
        session, trail, slug="limits", title="Limits", relation="prerequisite", concept=concept
    )
    await _seed_neighbour(
        session, trail, slug="continuity", title="Continuity", relation="related", concept=concept
    )
    generator = FakePrimerGenerator()

    await generate_concept_primer(
        session,
        generator,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )

    neighbour_context = generator.neighbour_contexts[0]
    assert neighbour_context["prerequisites"] == ["Limits"]
    assert neighbour_context["related"] == ["Continuity"]
    # The concept itself must never appear in its own neighbour context.
    all_titles = [t for titles in neighbour_context.values() for t in titles]
    assert "Derivatives" not in all_titles


async def test_generate_primer_includes_second_layer_in_nearby(session):
    workspace, trail, concept = await _seed_concept(session)
    prereq = await _seed_neighbour(
        session, trail, slug="limits", title="Limits", relation="prerequisite", concept=concept
    )
    # A node two hops out: prerequisite-of-prerequisite.
    await _seed_neighbour(
        session, trail, slug="functions", title="Functions", relation="prerequisite", concept=prereq
    )
    generator = FakePrimerGenerator()

    await generate_concept_primer(
        session,
        generator,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )

    neighbour_context = generator.neighbour_contexts[0]
    assert neighbour_context["prerequisites"] == ["Limits"]
    # "Functions" is one layer beyond the direct prerequisite -> nearby.
    assert "Functions" in neighbour_context["nearby"]
    assert "Limits" not in neighbour_context["nearby"]


async def test_stream_primer_cache_hit_emits_only_done(session, session_factory):
    workspace, trail, concept = await _seed_concept(session)
    generator = FakePrimerGenerator()
    # Prime the cache via the non-stream path.
    await generate_concept_primer(
        session,
        generator,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )
    calls_before = len(generator.calls)

    events = [
        event
        async for event in stream_concept_primer(
            session,
            generator,
            workspace_id=workspace.id,
            trail_id=trail.id,
            concept_id=concept.id,
            session_factory=session_factory,
            manager=PrimerGenerationManager(),
        )
    ]
    body = "".join(events)

    assert "event: done" in body
    assert "event: status" not in body
    assert "event: token" not in body
    # Cache hit => no additional model call.
    assert len(generator.calls) == calls_before


async def test_stream_primer_generation_emits_status_token_done(session, session_factory):
    workspace, trail, concept = await _seed_concept(session)
    concept_id = concept.id
    generator = FakePrimerGenerator()

    events = [
        event
        async for event in stream_concept_primer(
            session,
            generator,
            workspace_id=workspace.id,
            trail_id=trail.id,
            concept_id=concept_id,
            session_factory=session_factory,
            manager=PrimerGenerationManager(),
        )
    ]
    body = "".join(events)

    assert "event: status" in body
    assert '"status": "preparing"' in body
    assert "event: token" in body
    assert "event: done" in body
    # Ordering: status before first token before done.
    assert body.index("event: status") < body.index("event: token") < body.index("event: done")
    # The primer was persisted to the cache during streaming.
    cached = await _read_cached_primer(session_factory, concept_id)
    assert cached is not None
    assert len(cached.sample_questions) == 3


async def test_stream_primer_emits_thinking_excluded_from_parsed_json(session, session_factory):
    workspace, trail, concept = await _seed_concept(session)
    concept_id = concept.id
    generator = FakePrimerGenerator()

    events = [
        event
        async for event in stream_concept_primer(
            session,
            generator,
            workspace_id=workspace.id,
            trail_id=trail.id,
            concept_id=concept_id,
            session_factory=session_factory,
            manager=PrimerGenerationManager(),
        )
    ]
    body = "".join(events)

    # Reasoning is surfaced as its own event channel...
    assert "event: thinking" in body
    assert '"type": "thinking"' in body
    assert "orient the learner" in body
    # ...and arrives before the output tokens, mirroring reasoning models.
    assert body.index("event: thinking") < body.index("event: token")
    # The persisted primer is parsed from `token` content only: the reasoning
    # text must never leak into the structured overview/key terms.
    cached = await _read_cached_primer(session_factory, concept_id)
    assert cached is not None
    assert "orient the learner" not in cached.overview
    assert "orient the learner" not in json.dumps(cached.model_dump(mode="json"))


async def test_stream_primer_missing_concept_emits_error(session, session_factory):
    import uuid

    workspace, trail, _ = await _seed_concept(session)
    generator = FakePrimerGenerator()

    events = [
        event
        async for event in stream_concept_primer(
            session,
            generator,
            workspace_id=workspace.id,
            trail_id=trail.id,
            concept_id=uuid.uuid4(),
            session_factory=session_factory,
            manager=PrimerGenerationManager(),
        )
    ]
    body = "".join(events)

    assert "event: error" in body
    assert "not_found" in body


async def _read_cached_primer(session_factory, concept_id):
    """Read a concept's cached primer from a fresh session (post-detached-commit)."""
    async with session_factory() as fresh:
        concept = await fresh.get(ConceptNode, concept_id)
        return read_cached_primer(concept)


class _GatedPrimerGenerator(FakePrimerGenerator):
    """Streams the first token, then blocks until `release` is set.

    Lets a test simulate a mid-generation client disconnect: the consumer can
    break after the first token while the model call is still pending.
    """

    def __init__(self):
        super().__init__()
        self.first_token = asyncio.Event()
        self.release = asyncio.Event()
        self.stream_calls = 0

    async def generate_stream(self, *, concept, trail, neighbour_context):
        self.stream_calls += 1
        payload = json.dumps(self.output.model_dump(mode="json"))
        mid = len(payload) // 2
        yield ("token", payload[:mid])
        self.first_token.set()
        await self.release.wait()
        yield ("token", payload[mid:])


async def test_stream_primer_persists_when_consumer_disconnects(session, session_factory):
    workspace, trail, concept = await _seed_concept(session)
    concept_id = concept.id
    manager = PrimerGenerationManager()
    generator = _GatedPrimerGenerator()

    stream = stream_concept_primer(
        session,
        generator,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept_id,
        session_factory=session_factory,
        manager=manager,
    )
    # Consume up to the first preview token, then "disconnect" by closing the
    # SSE generator mid-flight (this is what a client refresh/navigate does).
    async for event in stream:
        if "event: token" in event:
            break
    await stream.aclose()

    # Let the detached generation finish; it owns its own session and commits
    # independently of the (now-closed) request stream.
    generator.release.set()
    await manager.drain()

    cached = await _read_cached_primer(session_factory, concept_id)
    assert cached is not None
    assert len(cached.key_terms) == 3
    # Exactly one model call despite the disconnect.
    assert generator.stream_calls == 1


async def test_concurrent_streams_share_single_generation(session, session_factory):
    workspace, trail, concept = await _seed_concept(session)
    manager = PrimerGenerationManager()
    generator = _GatedPrimerGenerator()

    # Subscribe to the manager directly (two near-simultaneous opens). The single
    # detached background task is the only DB writer, so this exercises dedup
    # without two request sessions racing the shared test connection.
    async def consume() -> str:
        return "".join(
            [
                event
                async for event in manager.stream(
                    generator,
                    session_factory,
                    workspace_id=workspace.id,
                    trail_id=trail.id,
                    concept_id=concept.id,
                )
            ]
        )

    first = asyncio.create_task(consume())
    second = asyncio.create_task(consume())
    # Let both attach to the SAME in-flight job before generation completes.
    await asyncio.wait_for(generator.first_token.wait(), timeout=1)
    generator.release.set()

    body_first, body_second = await asyncio.gather(first, second)

    # Both clients see a full, authoritative stream...
    assert "event: done" in body_first
    assert "event: done" in body_second
    # ...but only ONE model call ran for the concept.
    assert generator.stream_calls == 1
    assert await _read_cached_primer(session_factory, concept.id) is not None
