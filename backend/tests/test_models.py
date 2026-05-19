from typing import Any, overload

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.models.base import Base
from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.mastery import MasteryRecord, QuizAttempt
from backend.app.models.source import ConceptSourceLink, SourceRecord
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


@overload
async def save[T](session: AsyncSession, row: T) -> T: ...


@overload
async def save(session: AsyncSession, row: object, *rows: Any) -> tuple[Any, ...]: ...


async def save(session: AsyncSession, row: Any, *rows: Any) -> Any:
    all_rows = (row, *rows)
    session.add_all(all_rows)
    await session.commit()
    return row if len(all_rows) == 1 else all_rows


async def workspace(session: AsyncSession, name: str = "Default Workspace") -> Workspace:
    return await save(session, Workspace(name=name))


async def trail(
    session: AsyncSession, workspace: Workspace, title: str = "Linear Algebra"
) -> Trail:
    return await save(
        session,
        Trail(
            workspace_id=workspace.id,
            title=title,
            topic="Matrices",
            goal="Understand matrix multiplication",
            target_depth="understand",
        ),
    )


async def node(session: AsyncSession, trail: Trail, slug: str = "matrix-product") -> ConceptNode:
    return await save(
        session,
        ConceptNode(
            trail_id=trail.id,
            slug=slug,
            title="Matrix product",
            node_type="concept",
            concept_level="subtopic",
            difficulty="beginner",
            bloom_level="understand",
        ),
    )


@pytest.mark.asyncio
async def test_create_workspace(session):
    created = await workspace(session, "Phase 1")
    row = await session.get(Workspace, created.id)
    assert row.name == "Phase 1"


@pytest.mark.asyncio
async def test_create_trail(session):
    owner = await workspace(session)
    created = await trail(session, owner)
    row = await session.get(Trail, created.id)
    assert row.workspace_id == owner.id


@pytest.mark.asyncio
async def test_create_concept_node(session):
    created = await node(session, await trail(session, await workspace(session)))
    row = await session.get(ConceptNode, created.id)
    assert row.slug == "matrix-product"
    assert row.concept_level == "subtopic"
    assert row.mastery_check_labels == []
    assert row.metadata_json == {}


@pytest.mark.asyncio
async def test_slug_unique_within_trail(session):
    owner = await workspace(session)
    parent = await trail(session, owner)
    await node(session, parent, "same-slug")
    duplicate = ConceptNode(
        trail_id=parent.id,
        slug="same-slug",
        title="Duplicate",
        node_type="concept",
        concept_level="granular",
        difficulty="beginner",
        bloom_level="remember",
    )
    session.add(duplicate)
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_slug_reusable_across_trails(session):
    owner = await workspace(session)
    first = await node(session, await trail(session, owner, "Trail A"), "shared-slug")
    second = await node(session, await trail(session, owner, "Trail B"), "shared-slug")
    assert first.slug == second.slug
    assert first.trail_id != second.trail_id


@pytest.mark.asyncio
async def test_create_concept_edge(session):
    parent = await trail(session, await workspace(session))
    source = await node(session, parent, "source")
    target = await node(session, parent, "target")
    edge = await save(
        session,
        ConceptEdge(
            trail_id=parent.id,
            source_node_id=source.id,
            target_node_id=target.id,
            relation_type="prerequisite",
        ),
    )
    row = await session.get(ConceptEdge, edge.id)
    assert row.source_node_id == source.id
    assert row.target_node_id == target.id


@pytest.mark.asyncio
async def test_create_research_source(session):
    owner = await workspace(session)
    source = await save(
        session,
        SourceRecord(
            workspace_id=owner.id,
            origin="research_agent",
            access="public",
            title="Research source",
            url="https://example.com",
            include_on_public_export=True,
        ),
    )
    row = await session.get(SourceRecord, source.id)
    assert row.origin == "research_agent"
    assert row.include_on_public_export is True


@pytest.mark.asyncio
async def test_create_user_upload_source(session):
    source = await save(
        session,
        SourceRecord(
            workspace_id=(await workspace(session)).id,
            origin="user_upload",
            access="private",
            title="Uploaded source",
        ),
    )
    row = await session.get(SourceRecord, source.id)
    assert row.include_on_public_export is False


@pytest.mark.asyncio
async def test_public_export_excludes_user_upload(session):
    owner = await workspace(session)
    research = SourceRecord(
        workspace_id=owner.id,
        origin="research_agent",
        access="public",
        title="Public source",
        include_on_public_export=True,
    )
    upload = SourceRecord(
        workspace_id=owner.id,
        origin="user_upload",
        access="private",
        title="Private upload",
    )
    await save(session, research, upload)
    public_sources = list(
        await session.scalars(
            select(SourceRecord).where(SourceRecord.include_on_public_export.is_(True))
        )
    )
    assert research in public_sources
    assert upload not in public_sources


@pytest.mark.asyncio
async def test_concept_source_link(session):
    owner = await workspace(session)
    concept = await node(session, await trail(session, owner))
    source = await save(
        session,
        SourceRecord(
            workspace_id=owner.id,
            origin="manual",
            access="unknown",
            title="Manual citation",
        ),
    )
    link = await save(
        session,
        ConceptSourceLink(concept_id=concept.id, source_id=source.id, relation="reference"),
    )
    row = await session.scalar(select(ConceptSourceLink).where(ConceptSourceLink.id == link.id))
    assert row.source_id == source.id
    assert row.relation == "reference"


@pytest.mark.asyncio
async def test_create_mastery_record(session):
    owner = await workspace(session)
    concept = await node(session, await trail(session, owner))
    record = await save(
        session,
        MasteryRecord(
            workspace_id=owner.id,
            concept_id=concept.id,
            status="learning",
            bloom_level="understand",
            score=0.4,
        ),
    )
    row = await session.get(MasteryRecord, record.id)
    assert row.status == "learning"
    assert row.score == pytest.approx(0.4)


@pytest.mark.asyncio
async def test_create_quiz_attempt(session):
    concept = await node(session, await trail(session, await workspace(session)))
    attempt = await save(
        session,
        QuizAttempt(
            concept_id=concept.id,
            quiz_type="practice",
            questions_json=[{"id": "q1"}],
            answers_json=[{"question_id": "q1", "answer": "answer"}],
            evaluator_feedback="Helpful feedback",
            passed=True,
            score=0.8,
        ),
    )
    row = await session.get(QuizAttempt, attempt.id)
    assert row.quiz_type == "practice"
    assert row.score == pytest.approx(0.8)
