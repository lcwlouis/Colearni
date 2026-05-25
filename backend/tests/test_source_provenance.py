"""Source provenance safety tests for tutor context.

Verifies that:
  - Public/private linked source metadata appears in TutorContext.sources.
  - Prompt vars include title, URL, license, and relation for public sources.
  - Restricted and unknown-access sources are excluded.
  - Unlinked public sources are excluded.
  - Sources from other workspaces are excluded.
  - No raw content fields from metadata_json leak into prompt variables.

No live LLM calls are made.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.models.base import Base
from backend.app.models.concept import ConceptEdge, ConceptNode  # noqa: F401
from backend.app.models.conversation import Conversation, ConversationTurn  # noqa: F401
from backend.app.models.source import ConceptSourceLink, SourceRecord
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.services.conversations import TutorContext, build_tutor_context
from backend.app.services.tutor import _context_to_prompt_vars, _format_sources

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_concept(db_engine) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Seed workspace + trail + concept; return (ws_id, trail_id, concept_id)."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        ws = Workspace(name="Provenance WS")
        session.add(ws)
        await session.flush()

        trail = Trail(
            workspace_id=ws.id,
            title="Linear Algebra",
            topic="Linear Algebra",
            goal="Understand vectors",
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
            mastery_check_labels=[],
            metadata_json={},
        )
        session.add(concept)
        await session.commit()
        return ws.id, trail.id, concept.id


async def _make_source(
    db_engine,
    ws_id: uuid.UUID,
    *,
    origin: str = "research_agent",
    access: str = "public",
    title: str = "Test Source",
    url: str | None = "https://example.com",
    license_: str | None = "CC-BY",
    metadata_json: dict | None = None,
) -> uuid.UUID:
    """Create and persist a SourceRecord; return its id."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        src = SourceRecord(
            workspace_id=ws_id,
            origin=origin,
            access=access,
            title=title,
            url=url,
            license=license_,
            include_on_public_export=False,
            metadata_json=metadata_json or {},
        )
        session.add(src)
        await session.commit()
        return src.id


async def _link_source(
    db_engine,
    concept_id: uuid.UUID,
    source_id: uuid.UUID,
    relation: str = "reference",
) -> None:
    """Link a source to a concept via ConceptSourceLink."""
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        link = ConceptSourceLink(
            concept_id=concept_id,
            source_id=source_id,
            relation=relation,
        )
        session.add(link)
        await session.commit()


async def _build_context(db_session, ws_id, trail_id, concept_id) -> TutorContext:
    """Create a conversation and build TutorContext for the concept."""
    conv = Conversation(workspace_id=ws_id, trail_id=trail_id, concept_id=concept_id)
    db_session.add(conv)
    await db_session.flush()

    trail = await db_session.scalar(select(Trail).where(Trail.id == trail_id))
    concept = await db_session.scalar(select(ConceptNode).where(ConceptNode.id == concept_id))

    return await build_tutor_context(
        db_session,
        conversation=conv,
        concept=concept,
        trail=trail,
        learner_message="test",
        user_turn_index=0,
    )


# ---------------------------------------------------------------------------
# Test 1: Public linked source appears in context
# ---------------------------------------------------------------------------


async def test_public_linked_source_appears_in_context(db_engine, db_session):
    ws_id, trail_id, concept_id = await _seed_concept(db_engine)

    src_id = await _make_source(
        db_engine,
        ws_id,
        origin="research_agent",
        access="public",
        title="Khan Academy: Vectors",
        url="https://khanacademy.org/vectors",
        license_="CC-BY",
    )
    await _link_source(db_engine, concept_id, src_id, relation="reference")

    ctx = await _build_context(db_session, ws_id, trail_id, concept_id)

    assert len(ctx.sources) == 1
    source = ctx.sources[0]
    assert source.title == "Khan Academy: Vectors"
    assert source.url == "https://khanacademy.org/vectors"
    assert source.license == "CC-BY"
    assert source.origin == "research_agent"
    assert source.access == "public"
    assert source.relation == "reference"


# ---------------------------------------------------------------------------
# Test 2: Prompt vars include public source metadata
# ---------------------------------------------------------------------------


async def test_prompt_vars_include_public_source_metadata(db_engine, db_session):
    ws_id, trail_id, concept_id = await _seed_concept(db_engine)

    src_id = await _make_source(
        db_engine,
        ws_id,
        title="MIT OCW: Linear Algebra",
        url="https://ocw.mit.edu/linear-algebra",
        license_="CC-BY-SA",
    )
    await _link_source(db_engine, concept_id, src_id, relation="explains")

    ctx = await _build_context(db_session, ws_id, trail_id, concept_id)
    vars_ = _context_to_prompt_vars("socratic", ctx)

    assert "MIT OCW: Linear Algebra" in vars_["sources"]
    assert "https://ocw.mit.edu/linear-algebra" in vars_["sources"]
    assert "CC-BY-SA" in vars_["sources"]
    assert "explains" in vars_["sources"]
    assert vars_["sources"] != "none available"


# ---------------------------------------------------------------------------
# Test 3: User-upload source metadata is available when linked
# ---------------------------------------------------------------------------


async def test_user_upload_source_metadata_appears_in_context(db_engine, db_session):
    ws_id, trail_id, concept_id = await _seed_concept(db_engine)

    src_id = await _make_source(
        db_engine,
        ws_id,
        origin="user_upload",
        access="private",
        title="My Uploaded PDF",
        url=None,
    )
    await _link_source(db_engine, concept_id, src_id)

    ctx = await _build_context(db_session, ws_id, trail_id, concept_id)

    assert [source.title for source in ctx.sources] == ["My Uploaded PDF"]
    assert ctx.sources[0].origin == "user_upload"
    assert ctx.sources[0].access == "private"
    vars_ = _context_to_prompt_vars("socratic", ctx)
    assert "My Uploaded PDF" in vars_["sources"]


async def test_user_upload_source_private_access_included(db_engine, db_session):
    ws_id, trail_id, concept_id = await _seed_concept(db_engine)

    src_id = await _make_source(
        db_engine,
        ws_id,
        origin="user_upload",
        access="private",
        title="Private Upload",
    )
    await _link_source(db_engine, concept_id, src_id)

    ctx = await _build_context(db_session, ws_id, trail_id, concept_id)
    assert [source.title for source in ctx.sources] == ["Private Upload"]


# ---------------------------------------------------------------------------
# Test 4: Private sources are included; restricted/unknown sources are excluded
# ---------------------------------------------------------------------------


async def test_private_access_source_included(db_engine, db_session):
    ws_id, trail_id, concept_id = await _seed_concept(db_engine)

    src_id = await _make_source(
        db_engine,
        ws_id,
        origin="manual",
        access="private",
        title="Private Notes",
    )
    await _link_source(db_engine, concept_id, src_id)

    ctx = await _build_context(db_session, ws_id, trail_id, concept_id)
    assert [source.title for source in ctx.sources] == ["Private Notes"]
    assert "Private Notes" in _context_to_prompt_vars("socratic", ctx)["sources"]


async def test_restricted_access_source_excluded(db_engine, db_session):
    ws_id, trail_id, concept_id = await _seed_concept(db_engine)

    src_id = await _make_source(
        db_engine,
        ws_id,
        origin="research_agent",
        access="restricted",
        title="Paywalled Paper",
    )
    await _link_source(db_engine, concept_id, src_id)

    ctx = await _build_context(db_session, ws_id, trail_id, concept_id)
    assert ctx.sources == []
    assert "Paywalled Paper" not in _context_to_prompt_vars("socratic", ctx)["sources"]


async def test_unknown_access_source_excluded(db_engine, db_session):
    """unknown-access sources are excluded by default (no redistribution of content)."""
    ws_id, trail_id, concept_id = await _seed_concept(db_engine)

    src_id = await _make_source(
        db_engine,
        ws_id,
        origin="research_agent",
        access="unknown",
        title="Unknown Access Blog",
    )
    await _link_source(db_engine, concept_id, src_id)

    ctx = await _build_context(db_session, ws_id, trail_id, concept_id)
    assert ctx.sources == []
    assert "Unknown Access Blog" not in _context_to_prompt_vars("socratic", ctx)["sources"]


# ---------------------------------------------------------------------------
# Test 5: Unlinked public source is excluded
# ---------------------------------------------------------------------------


async def test_unlinked_public_source_excluded(db_engine, db_session):
    ws_id, trail_id, concept_id = await _seed_concept(db_engine)

    # Create source in same workspace but do NOT link it to the concept.
    await _make_source(
        db_engine,
        ws_id,
        origin="research_agent",
        access="public",
        title="Unlinked Public Source",
        url="https://example.com/unlinked",
    )
    # No _link_source call.

    ctx = await _build_context(db_session, ws_id, trail_id, concept_id)
    assert ctx.sources == []
    assert "Unlinked Public Source" not in _context_to_prompt_vars("socratic", ctx)["sources"]


# ---------------------------------------------------------------------------
# Test 6: Other workspace public source is excluded
# ---------------------------------------------------------------------------


async def test_other_workspace_source_excluded_by_tutor_context(db_engine, db_session):
    ws_id, trail_id, concept_id = await _seed_concept(db_engine)

    # Create a second workspace with its own source.
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        other_ws = Workspace(name="Other WS")
        session.add(other_ws)
        await session.flush()
        other_src = SourceRecord(
            workspace_id=other_ws.id,
            origin="research_agent",
            access="public",
            title="Other WS Source",
            url="https://other.com/source",
            license=None,
            include_on_public_export=False,
            metadata_json={},
        )
        session.add(other_src)
        await session.flush()
        other_src_id = other_src.id
        await session.commit()

    # Deliberately create a cross-workspace link to prove the source loader's
    # workspace filter blocks it even if the association row exists.
    await _link_source(db_engine, concept_id, other_src_id)

    ctx = await _build_context(db_session, ws_id, trail_id, concept_id)

    titles = [s.title for s in ctx.sources]
    assert "Other WS Source" not in titles


async def test_legacy_load_safe_sources_excludes_other_workspace_source(db_engine):
    ws_id, _, concept_id = await _seed_concept(db_engine)
    async_session = async_sessionmaker(db_engine, expire_on_commit=False)
    async with async_session() as session:
        other_ws = Workspace(name="Other WS Legacy")
        session.add(other_ws)
        await session.flush()
        other_src = SourceRecord(
            workspace_id=other_ws.id,
            origin="research_agent",
            access="public",
            title="Other WS Legacy Source",
            url="https://other.com/legacy-source",
            license=None,
            include_on_public_export=False,
            metadata_json={},
        )
        session.add(other_src)
        await session.flush()
        other_src_id = other_src.id
        await session.commit()

    # Legacy public-only helper is kept for this direct unit test only.
    await _link_source(db_engine, concept_id, other_src_id)

    from backend.app.services.conversations import _load_safe_sources

    async with async_session() as session:
        sources = await _load_safe_sources(
            session,
            concept_id=concept_id,
            workspace_id=ws_id,
        )

    titles = [s.title for s in sources]
    assert "Other WS Legacy Source" not in titles


# ---------------------------------------------------------------------------
# Test 7: No raw content fields from metadata_json leak into prompt vars
# ---------------------------------------------------------------------------


async def test_no_raw_content_fields_in_prompt_vars(db_engine, db_session):
    """metadata_json with sensitive strings must never appear in prompt variables."""
    ws_id, trail_id, concept_id = await _seed_concept(db_engine)

    src_id = await _make_source(
        db_engine,
        ws_id,
        origin="research_agent",
        access="public",
        title="Safe Title",
        url="https://example.com",
        license_="MIT",
        metadata_json={"raw_text": "SECRET RAW CONTENT", "embedding": [0.1, 0.2, 0.3]},
    )
    await _link_source(db_engine, concept_id, src_id)

    ctx = await _build_context(db_session, ws_id, trail_id, concept_id)

    # The source must appear (it is public and linked).
    assert len(ctx.sources) == 1

    # But the prompt vars must not contain the raw content.
    vars_ = _context_to_prompt_vars("socratic", ctx)
    assert "SECRET RAW CONTENT" not in vars_["sources"]
    assert "embedding" not in vars_["sources"]

    # Verify that no field from the TutorSourceMetadata exposes metadata_json.
    src_meta = ctx.sources[0]
    # The dataclass has only whitelisted fields; metadata_json is not one of them.
    assert not hasattr(src_meta, "metadata_json")


# ---------------------------------------------------------------------------
# Test 8: Multiple public sources all appear; correct count
# ---------------------------------------------------------------------------


async def test_multiple_public_sources_all_appear(db_engine, db_session):
    ws_id, trail_id, concept_id = await _seed_concept(db_engine)

    for i in range(3):
        src_id = await _make_source(
            db_engine,
            ws_id,
            title=f"Source {i}",
            url=f"https://example.com/{i}",
        )
        await _link_source(db_engine, concept_id, src_id, relation="reference")

    ctx = await _build_context(db_session, ws_id, trail_id, concept_id)
    assert len(ctx.sources) == 3

    vars_ = _context_to_prompt_vars("socratic", ctx)
    for i in range(3):
        assert f"Source {i}" in vars_["sources"]


# ---------------------------------------------------------------------------
# Test 9: Source without URL renders correctly
# ---------------------------------------------------------------------------


async def test_source_without_url_renders_correctly(db_engine, db_session):
    ws_id, trail_id, concept_id = await _seed_concept(db_engine)

    src_id = await _make_source(
        db_engine,
        ws_id,
        title="Textbook Reference",
        url=None,
        license_=None,
    )
    await _link_source(db_engine, concept_id, src_id, relation="explains")

    ctx = await _build_context(db_session, ws_id, trail_id, concept_id)
    vars_ = _context_to_prompt_vars("socratic", ctx)

    assert "Textbook Reference" in vars_["sources"]
    # No URL parentheses when url is None.
    assert "(None)" not in vars_["sources"]
    assert "()" not in vars_["sources"]
    # Unknown license rendered explicitly.
    assert "license: unknown" in vars_["sources"]


# ---------------------------------------------------------------------------
# Unit test: _format_sources
# ---------------------------------------------------------------------------


def test_format_sources_empty_returns_none_available():
    assert _format_sources([]) == "none available"


def test_format_sources_single_with_url_and_license():
    from backend.app.services.conversations import TutorSourceMetadata

    src = TutorSourceMetadata(
        id=uuid.uuid4(),
        title="Great Resource",
        url="https://example.com",
        origin="research_agent",
        access="public",
        license="CC-BY",
        relation="reference",
    )
    result = _format_sources([src])
    assert "Great Resource" in result
    assert "https://example.com" in result
    assert "CC-BY" in result
    assert "reference" in result


def test_format_sources_no_url_no_license():
    from backend.app.services.conversations import TutorSourceMetadata

    src = TutorSourceMetadata(
        id=uuid.uuid4(),
        title="Book Chapter",
        url=None,
        origin="manual",
        access="public",
        license=None,
        relation="explains",
    )
    result = _format_sources([src])
    assert "Book Chapter" in result
    assert "license: unknown" in result
    assert "(None)" not in result
