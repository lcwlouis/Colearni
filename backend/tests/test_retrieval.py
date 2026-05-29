import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.agents.provider_tools import ProviderToolDefinition
from backend.app.agents.retrieval_tools import (
    GET_CONCEPT_SOURCES_TOOL,
    GET_GRAPH_NEIGHBOURHOOD_TOOL,
    RETRIEVAL_TOOLS,
    SEARCH_SOURCES_TOOL,
)
from backend.app.models.base import Base
from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.conversation import Conversation
from backend.app.models.source import ConceptSourceLink, SourceChunk, SourceRecord, SourceRevision
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.services.conversations import build_tutor_context
from backend.app.services.retrieval import (
    get_concept_sources_for_tutor,
    get_graph_neighbourhood,
    search_sources_by_title,
    search_sources_by_text,
)


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


async def test_get_concept_sources_for_tutor_filters_orders_and_sanitizes(
    db_session: AsyncSession,
):
    workspace, _, concept = await _seed_concept(db_session)
    other_workspace, _, _ = await _seed_concept(db_session, name="Other")
    public_source = await _source(
        db_session,
        workspace.id,
        title="Beta Public Research",
        origin="research_agent",
        access="public",
        url="https://example.com/beta",
    )
    private_upload = await _source(
        db_session,
        workspace.id,
        title="Alpha Private Upload",
        origin="user_upload",
        access="private",
        with_revision=True,
    )
    restricted = await _source(db_session, workspace.id, title="Restricted", access="restricted")
    unknown = await _source(db_session, workspace.id, title="Unknown", access="unknown")
    other_workspace_source = await _source(
        db_session,
        other_workspace.id,
        title="Other Workspace Source",
    )
    await _link(db_session, public_source, concept, relation="reference")
    await _link(db_session, private_upload, concept, relation="primary")
    await _link(db_session, restricted, concept, relation="primary")
    await _link(db_session, unknown, concept, relation="primary")
    await _link(db_session, other_workspace_source, concept, relation="primary")

    sources = await get_concept_sources_for_tutor(
        db_session,
        workspace_id=workspace.id,
        concept_id=concept.id,
        max_sources=10,
    )

    assert [source.title for source in sources] == [
        "Alpha Private Upload",
        "Beta Public Research",
    ]
    assert sources[0].origin == "user_upload"
    assert sources[0].access == "private"
    assert sources[0].url is None
    assert sources[1].origin == "research_agent"
    assert sources[1].access == "public"
    assert sources[1].url == "https://example.com/beta"
    rendered = repr(sources)
    assert "object_key" not in rendered
    assert "content_hash" not in rendered
    assert "secret/object/key" not in rendered
    assert "sha256:secret" not in rendered


async def test_get_concept_sources_for_tutor_respects_cap(db_session: AsyncSession):
    workspace, _, concept = await _seed_concept(db_session)
    for index in range(15):
        source = await _source(db_session, workspace.id, title=f"Cap Source {index:02d}")
        await _link(db_session, source, concept, relation="reference")

    sources = await get_concept_sources_for_tutor(
        db_session,
        workspace_id=workspace.id,
        concept_id=concept.id,
        max_sources=15,
    )

    assert len(sources) == 10


@pytest.mark.parametrize(
    ("access", "origin"),
    [("public", "research_agent"), ("private", "user_upload")],
)
async def test_get_concept_sources_for_tutor_returns_allowed_accesses(
    db_session: AsyncSession,
    access: str,
    origin: str,
):
    workspace, _, concept = await _seed_concept(db_session)
    source = await _source(
        db_session,
        workspace.id,
        title=f"{access} source",
        access=access,
        origin=origin,
    )
    await _link(db_session, source, concept, relation="primary")

    sources = await get_concept_sources_for_tutor(
        db_session,
        workspace_id=workspace.id,
        concept_id=concept.id,
    )

    assert [(source.access, source.origin) for source in sources] == [(access, origin)]


@pytest.mark.parametrize("access", ["restricted", "unknown"])
async def test_get_concept_sources_for_tutor_excludes_disallowed_access(
    db_session: AsyncSession,
    access: str,
):
    workspace, _, concept = await _seed_concept(db_session)
    source = await _source(db_session, workspace.id, title=f"{access} source", access=access)
    await _link(db_session, source, concept, relation="primary")

    sources = await get_concept_sources_for_tutor(
        db_session,
        workspace_id=workspace.id,
        concept_id=concept.id,
    )

    assert sources == []


async def test_get_concept_sources_for_tutor_respects_requested_lower_limit(
    db_session: AsyncSession,
):
    workspace, _, concept = await _seed_concept(db_session)
    for index in range(3):
        source = await _source(db_session, workspace.id, title=f"Limited Source {index}")
        await _link(db_session, source, concept, relation="reference")

    sources = await get_concept_sources_for_tutor(
        db_session,
        workspace_id=workspace.id,
        concept_id=concept.id,
        max_sources=2,
    )

    assert len(sources) == 2


async def test_get_concept_sources_for_tutor_excludes_concept_from_different_workspace(
    db_session: AsyncSession,
):
    workspace, _, _ = await _seed_concept(db_session)
    _, _, other_concept = await _seed_concept(db_session, name="Other Workspace")
    source = await _source(db_session, workspace.id, title="Local Source")
    await _link(db_session, source, other_concept, relation="primary")

    sources = await get_concept_sources_for_tutor(
        db_session,
        workspace_id=workspace.id,
        concept_id=other_concept.id,
    )

    assert sources == []


@pytest.mark.parametrize("max_sources", [0, -1])
async def test_get_concept_sources_for_tutor_empty_for_non_positive_limit(
    db_session: AsyncSession,
    max_sources: int,
):
    workspace, _, concept = await _seed_concept(db_session)
    source = await _source(db_session, workspace.id, title="Source")
    await _link(db_session, source, concept, relation="primary")

    sources = await get_concept_sources_for_tutor(
        db_session,
        workspace_id=workspace.id,
        concept_id=concept.id,
        max_sources=max_sources,
    )

    assert sources == []


def test_get_graph_neighbourhood_returns_expected_edges():
    concept = _node("target", "Target")
    prerequisite = _node("prereq", "Prerequisite")
    contained = _node("contained", "Contained")
    containing = _node("parent", "Parent")
    related = _node("related", "Related")
    application = _node("application", "Application")
    edges = [
        _edge(prerequisite, concept, "prerequisite"),
        _edge(concept, contained, "contains"),
        _edge(containing, concept, "contains"),
        _edge(concept, related, "related"),
        _edge(application, concept, "application"),
    ]

    neighbourhood = get_graph_neighbourhood(
        concept=concept,
        all_nodes=[concept, prerequisite, contained, containing, related, application],
        edges=edges,
    )

    assert neighbourhood["prerequisites"] == [prerequisite]
    assert neighbourhood["contained_nodes"] == [contained]
    assert neighbourhood["containing_nodes"] == [containing]
    assert neighbourhood["related"] == [related]
    assert neighbourhood["application_nodes"] == [application]


def test_get_graph_neighbourhood_returns_empty_lists_without_edges():
    concept = _node("target", "Target")

    neighbourhood = get_graph_neighbourhood(concept=concept, all_nodes=[concept], edges=[])

    assert neighbourhood == {
        "prerequisites": [],
        "contained_nodes": [],
        "containing_nodes": [],
        "related": [],
        "application_nodes": [],
    }


def test_get_graph_neighbourhood_caps_each_type():
    concept = _node("target", "Target")
    prerequisites = [_node(f"prereq-{index}", f"Prereq {index}") for index in range(8)]

    neighbourhood = get_graph_neighbourhood(
        concept=concept,
        all_nodes=[concept, *prerequisites],
        edges=[_edge(prerequisite, concept, "prerequisite") for prerequisite in prerequisites],
    )

    assert len(neighbourhood["prerequisites"]) == 5


async def test_search_sources_by_title_matches_case_insensitive_and_uses_empty_relation(
    db_session: AsyncSession,
):
    workspace, _, _ = await _seed_concept(db_session)
    await _source(db_session, workspace.id, title="Linear Algebra Notes")

    matches = await search_sources_by_title(
        db_session,
        workspace_id=workspace.id,
        query="algebra",
    )
    misses = await search_sources_by_title(
        db_session,
        workspace_id=workspace.id,
        query="calculus",
    )

    assert [source.title for source in matches] == ["Linear Algebra Notes"]
    assert matches[0].relation == ""
    assert misses == []


async def test_search_sources_by_title_filters_concept_access_and_workspace(
    db_session: AsyncSession,
):
    workspace, _, concept = await _seed_concept(db_session)
    other_concept = await _concept(db_session, concept.trail_id, slug="matrices", title="Matrices")
    other_workspace, _, _ = await _seed_concept(db_session, name="Other Workspace")
    local = await _source(db_session, workspace.id, title="Guide for Vectors")
    other_concept_source = await _source(db_session, workspace.id, title="Guide for Matrices")
    other_workspace_source = await _source(db_session, other_workspace.id, title="Guide Elsewhere")
    restricted = await _source(
        db_session,
        workspace.id,
        title="Guide Restricted",
        access="restricted",
    )
    await _link(db_session, local, concept, relation="primary")
    await _link(db_session, other_concept_source, other_concept, relation="primary")
    await _link(db_session, other_workspace_source, concept, relation="primary")
    await _link(db_session, restricted, concept, relation="primary")

    matches = await search_sources_by_title(
        db_session,
        workspace_id=workspace.id,
        query="guide",
        concept_id=concept.id,
    )

    assert [source.title for source in matches] == ["Guide for Vectors"]
    assert matches[0].relation == "primary"


async def test_search_sources_by_title_respects_cap(db_session: AsyncSession):
    workspace, _, _ = await _seed_concept(db_session)
    for index in range(15):
        await _source(db_session, workspace.id, title=f"Cap Match {index:02d}")

    matches = await search_sources_by_title(
        db_session,
        workspace_id=workspace.id,
        query="cap match",
        max_results=15,
    )

    assert len(matches) == 10


async def test_search_sources_by_title_returns_private_upload(db_session: AsyncSession):
    workspace, _, _ = await _seed_concept(db_session)
    await _source(
        db_session,
        workspace.id,
        title="Private Upload Notes",
        origin="user_upload",
        access="private",
    )

    matches = await search_sources_by_title(
        db_session,
        workspace_id=workspace.id,
        query="upload",
    )

    assert [(source.title, source.origin, source.access) for source in matches] == [
        ("Private Upload Notes", "user_upload", "private")
    ]


@pytest.mark.parametrize("max_results", [0, -1])
async def test_search_sources_by_title_empty_for_non_positive_limit(
    db_session: AsyncSession,
    max_results: int,
):
    workspace, _, _ = await _seed_concept(db_session)
    await _source(db_session, workspace.id, title="Searchable")

    matches = await search_sources_by_title(
        db_session,
        workspace_id=workspace.id,
        query="search",
        max_results=max_results,
    )

    assert matches == []


async def test_search_sources_by_title_orders_linked_results_by_relation(
    db_session: AsyncSession,
):
    workspace, _, concept = await _seed_concept(db_session)
    reference = await _source(db_session, workspace.id, title="Alpha Linked Match")
    primary = await _source(db_session, workspace.id, title="Zeta Linked Match")
    await _link(db_session, reference, concept, relation="reference")
    await _link(db_session, primary, concept, relation="primary")

    matches = await search_sources_by_title(
        db_session,
        workspace_id=workspace.id,
        query="linked match",
        concept_id=concept.id,
    )

    assert [(source.title, source.relation) for source in matches] == [
        ("Zeta Linked Match", "primary"),
        ("Alpha Linked Match", "reference"),
    ]


async def test_search_sources_by_title_excludes_concept_from_different_workspace(
    db_session: AsyncSession,
):
    workspace, _, _ = await _seed_concept(db_session)
    _, _, other_concept = await _seed_concept(db_session, name="Other Workspace")
    source = await _source(db_session, workspace.id, title="Cross Workspace Match")
    await _link(db_session, source, other_concept, relation="primary")

    matches = await search_sources_by_title(
        db_session,
        workspace_id=workspace.id,
        query="cross",
        concept_id=other_concept.id,
    )

    assert matches == []


async def test_search_sources_by_text_falls_back_to_ilike_with_line_metadata(
    db_session: AsyncSession,
):
    workspace, _, _ = await _seed_concept(db_session)
    source = await _source(
        db_session,
        workspace.id,
        title="Vector Notes",
        origin="user_upload",
        access="private",
    )
    revision = SourceRevision(
        workspace_id=workspace.id,
        source_id=source.id,
        revision_number=1,
        object_key="vector-notes.txt",
        content_hash="sha256:vector-notes",
        content_type="text/plain",
        file_size_bytes=12,
        parser_name="plaintext",
        parser_version="parser-pipeline-v1",
        status="parsed",
        raw_text="Vectors are quantities with magnitude and direction.",
        metadata_json={},
    )
    db_session.add(revision)
    await db_session.flush()
    db_session.add(
        SourceChunk(
            source_revision_id=revision.id,
            workspace_id=workspace.id,
            chunk_index=0,
            text="Vectors are quantities with magnitude and direction.",
            char_start=0,
            char_end=52,
            line_start=1,
            line_end=1,
            section_heading="Vectors",
            embedding=None,
        )
    )
    await db_session.flush()

    fake_client = AsyncMock()
    fake_client.embed.return_value = None
    with patch("backend.app.services.retrieval.EmbeddingClient.from_settings", return_value=fake_client):
        matches = await search_sources_by_text(
            "magnitude",
            workspace.id,
            db_session,
        )

    assert len(matches) == 1
    assert matches[0].source_id == source.id
    assert matches[0].source_revision_id == revision.id
    assert matches[0].source_title == "Vector Notes"
    assert matches[0].section_heading == "Vectors"
    assert matches[0].line_start == 1
    assert matches[0].similarity is None


def test_retrieval_tool_definitions_instantiate():
    assert isinstance(GET_CONCEPT_SOURCES_TOOL, ProviderToolDefinition)
    assert GET_CONCEPT_SOURCES_TOOL.parameters["required"] == []
    assert GET_GRAPH_NEIGHBOURHOOD_TOOL.parameters["required"] == []
    assert SEARCH_SOURCES_TOOL.parameters["required"] == ["query"]
    assert len(RETRIEVAL_TOOLS) == 4


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        (GET_CONCEPT_SOURCES_TOOL, {"concept_id": str(uuid.uuid4())}),
        (GET_CONCEPT_SOURCES_TOOL, {}),
        (GET_GRAPH_NEIGHBOURHOOD_TOOL, {"concept_id": str(uuid.uuid4())}),
        (GET_GRAPH_NEIGHBOURHOOD_TOOL, {}),
        (SEARCH_SOURCES_TOOL, {"query": "vectors"}),
    ],
)
def test_retrieval_tool_definitions_validate_required_arguments(
    tool: ProviderToolDefinition,
    arguments: dict[str, str],
):
    assert tool.validate_arguments(arguments) == arguments


@pytest.mark.parametrize("tool", RETRIEVAL_TOOLS)
def test_retrieval_tool_definitions_reject_extra_arguments(tool: ProviderToolDefinition):
    arguments = {field: "x" for field in tool.parameters.get("required", [])}
    arguments["unexpected"] = "x"

    with pytest.raises(ValueError):
        tool.validate_arguments(arguments)


async def test_build_tutor_context_includes_private_upload_source(db_session: AsyncSession):
    workspace, trail, concept = await _seed_concept(db_session)
    conversation = Conversation(
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )
    public_source = await _source(
        db_session,
        workspace.id,
        title="Public Research",
        origin="research_agent",
        access="public",
    )
    private_upload = await _source(
        db_session,
        workspace.id,
        title="Private Upload",
        origin="user_upload",
        access="private",
    )
    await _link(db_session, public_source, concept, relation="reference")
    await _link(db_session, private_upload, concept, relation="primary")
    db_session.add(conversation)
    await db_session.flush()

    context = await build_tutor_context(
        db_session,
        conversation=conversation,
        concept=concept,
        trail=trail,
        learner_message="teach me",
        user_turn_index=0,
    )

    assert {source.title for source in context.sources} == {"Public Research", "Private Upload"}


async def _seed_concept(
    session: AsyncSession,
    *,
    name: str = "Workspace",
) -> tuple[Workspace, Trail, ConceptNode]:
    workspace = Workspace(name=name)
    session.add(workspace)
    await session.flush()
    trail = Trail(
        workspace_id=workspace.id,
        title=f"{name} Trail",
        topic="Math",
        goal="Learn",
        target_depth="understand",
    )
    session.add(trail)
    await session.flush()
    concept = ConceptNode(
        trail_id=trail.id,
        slug="vectors",
        title="Vectors",
        node_type="concept",
        concept_level="topic",
        difficulty="beginner",
        bloom_level="understand",
        mastery_check_labels=["explain vectors"],
        metadata_json={},
    )
    session.add(concept)
    await session.flush()
    return workspace, trail, concept


async def _concept(
    session: AsyncSession,
    trail_id: uuid.UUID,
    *,
    slug: str,
    title: str,
) -> ConceptNode:
    concept = ConceptNode(
        trail_id=trail_id,
        slug=slug,
        title=title,
        node_type="concept",
        concept_level="topic",
        difficulty="beginner",
        bloom_level="understand",
        mastery_check_labels=[f"explain {title}"],
        metadata_json={},
    )
    session.add(concept)
    await session.flush()
    return concept


async def _source(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    title: str,
    origin: str = "research_agent",
    access: str = "public",
    url: str | None = None,
    with_revision: bool = False,
) -> SourceRecord:
    source = SourceRecord(
        workspace_id=workspace_id,
        origin=origin,
        access=access,
        title=title,
        url=url,
        license=None,
        include_on_public_export=False,
        metadata_json={},
    )
    session.add(source)
    await session.flush()
    if with_revision:
        session.add(
            SourceRevision(
                workspace_id=workspace_id,
                source_id=source.id,
                revision_number=1,
                object_key="secret/object/key",
                content_hash="sha256:secret",
                content_type="text/plain",
                file_size_bytes=6,
                parser_name="none",
                parser_version="upload-only-v1",
                status="pending_parse",
                metadata_json={},
            )
        )
        await session.flush()
    return source


async def _link(
    session: AsyncSession,
    source: SourceRecord,
    concept: ConceptNode,
    *,
    relation: str,
) -> None:
    session.add(ConceptSourceLink(source_id=source.id, concept_id=concept.id, relation=relation))
    await session.flush()


def _node(slug: str, title: str) -> ConceptNode:
    return ConceptNode(
        id=uuid.uuid4(),
        trail_id=uuid.uuid4(),
        slug=slug,
        title=title,
        node_type="concept",
        concept_level="topic",
        difficulty="beginner",
        bloom_level="understand",
        mastery_check_labels=[],
        metadata_json={},
    )


def _edge(source: ConceptNode, target: ConceptNode, relation_type: str) -> ConceptEdge:
    return ConceptEdge(
        trail_id=source.trail_id,
        source_node_id=source.id,
        target_node_id=target.id,
        relation_type=relation_type,
    )
