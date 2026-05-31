"""Artifact foundation tests (Phase 15a).

Covers strict-envelope validation, the create-service round-trip (workspace +
trail scoping), citation dropping, and public-export provenance gating.
No live LLM calls are made.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.models.base import Base
from backend.app.models.concept import ConceptNode
from backend.app.models.source import SourceRecord, SourceRevision
from backend.app.models.trail import Trail
from backend.app.models.workspace import Workspace
from backend.app.services.artifacts import (
    can_include_artifact_in_public_export,
    create_artifact,
    get_artifact,
    list_artifacts,
    validate_artifact_payload,
)

# ---------------------------------------------------------------------------
# Fixtures (in-memory sqlite, mirrors test_tutor_service.py)
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


async def _seed_workspace_trail(session) -> tuple[Workspace, Trail]:
    workspace = Workspace(name="WS")
    session.add(workspace)
    await session.flush()
    trail = Trail(
        workspace_id=workspace.id,
        title="Trail",
        topic="Topic",
        goal="Goal",
        target_depth="understand",
    )
    session.add(trail)
    await session.flush()
    return workspace, trail


async def _seed_concept(session, trail: Trail) -> ConceptNode:
    concept = ConceptNode(
        trail_id=trail.id,
        slug=f"concept-{uuid.uuid4().hex[:8]}",
        title="Concept",
        node_type="concept",
        concept_level="subtopic",
        difficulty="intermediate",
        bloom_level="understand",
        mastery_check_labels=[],
        metadata_json={},
    )
    session.add(concept)
    await session.flush()
    return concept


async def _seed_source_with_revision(
    session,
    *,
    workspace_id: uuid.UUID,
    origin: str = "research_agent",
    access: str = "public",
    include_on_public_export: bool = True,
) -> SourceRevision:
    source = SourceRecord(
        workspace_id=workspace_id,
        origin=origin,
        access=access,
        title="Source",
        url="https://example.com",
        include_on_public_export=include_on_public_export,
        metadata_json={},
    )
    session.add(source)
    await session.flush()
    digest = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()
    revision = SourceRevision(
        workspace_id=workspace_id,
        source_id=source.id,
        revision_number=1,
        object_key=f"workspaces/{workspace_id}/sources/{source.id}/revisions/1/{digest}.txt",
        content_hash=f"sha256:{digest}",
        content_type="text/plain",
        file_size_bytes=10,
        parser_name="none",
        parser_version="upload-only-v1",
        status="parsed",
    )
    session.add(revision)
    await session.flush()
    return revision


# ---------------------------------------------------------------------------
# Payload builders
# ---------------------------------------------------------------------------


def _worked_example_payload(**overrides) -> dict:
    payload = {
        "artifact_version": 1,
        "kind": "worked_example",
        "title": "Solving 2x = 4",
        "caption": None,
        "text_fallback": "Step 1: divide both sides by 2. Answer: x = 2.",
        "provenance": {
            "source_ids": [],
            "visibility": "local_only",
            "citations": [],
        },
        "data": {
            "steps": [
                {"label": "Isolate x", "detail": "Divide both sides by 2"},
            ],
            "final_answer": "x = 2",
        },
    }
    payload.update(overrides)
    return payload


def _comparison_card_payload(**overrides) -> dict:
    payload = {
        "artifact_version": 1,
        "kind": "comparison_card",
        "title": "Lists vs Tuples",
        "caption": "A quick comparison",
        "text_fallback": "Lists are mutable; tuples are immutable.",
        "provenance": {
            "source_ids": [],
            "visibility": "local_only",
            "citations": [],
        },
        "data": {
            "items": ["list", "tuple"],
            "criteria": [
                {"label": "Mutable", "values": ["yes", "no"]},
                {"label": "Syntax", "values": ["[]", "()"]},
            ],
        },
    }
    payload.update(overrides)
    return payload


def _timeline_payload(**overrides) -> dict:
    payload = {
        "artifact_version": 1,
        "kind": "timeline",
        "title": "Space race milestones",
        "caption": None,
        "text_fallback": "1957 Sputnik. 1969 Apollo 11 lands on the Moon.",
        "provenance": {
            "source_ids": [],
            "visibility": "local_only",
            "citations": [],
        },
        "data": {
            "events": [
                {"label": "Sputnik launched", "when": "1957", "note": None},
                {"label": "Apollo 11", "when": "1969", "note": "First Moon landing"},
            ],
        },
    }
    payload.update(overrides)
    return payload


def _mini_graph_payload(**overrides) -> dict:
    payload = {
        "artifact_version": 1,
        "kind": "mini_graph",
        "title": "Water cycle",
        "caption": "A tiny graph",
        "text_fallback": "Evaporation -> Condensation -> Precipitation.",
        "provenance": {
            "source_ids": [],
            "visibility": "local_only",
            "citations": [],
        },
        "data": {
            "nodes": [
                {"id": "a", "label": "Evaporation"},
                {"id": "b", "label": "Condensation"},
                {"id": "c", "label": "Precipitation"},
            ],
            "edges": [
                {"source": "a", "target": "b", "label": "rises"},
                {"source": "b", "target": "c", "label": None},
            ],
        },
    }
    payload.update(overrides)
    return payload


def _simulation_slider_payload(**overrides) -> dict:
    payload = {
        "artifact_version": 1,
        "kind": "simulation_slider",
        "title": "Linear function explorer",
        "caption": None,
        "text_fallback": "y = m*x + b. Drag the sliders to change slope and intercept.",
        "provenance": {
            "source_ids": [],
            "visibility": "local_only",
            "citations": [],
        },
        "data": {
            "sim_kind": "linear",
            "parameters": [
                {"name": "m", "label": "Slope", "min": -5, "max": 5, "default": 2, "step": 0.1},
                {"name": "b", "label": "Intercept", "min": -10, "max": 10, "default": 1},
            ],
            "x_label": "x",
            "y_label": "y",
            "x_range": {"min": 0, "max": 10},
            "prompt": "Predict what happens to the line as the slope grows.",
        },
    }
    payload.update(overrides)
    return payload


async def test_worked_example_validates_and_round_trips(db_session):
    workspace, trail = await _seed_workspace_trail(db_session)
    concept = await _seed_concept(db_session, trail)

    envelope = validate_artifact_payload(_worked_example_payload())
    assert envelope.kind == "worked_example"

    artifact = await create_artifact(
        db_session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        envelope=envelope,
    )
    assert artifact.artifact_type == "worked_example"
    assert artifact.visibility == "local_only"
    assert artifact.payload_json["data"]["final_answer"] == "x = 2"

    listed = await list_artifacts(db_session, workspace_id=workspace.id, trail_id=trail.id)
    assert [a.id for a in listed] == [artifact.id]

    fetched = await get_artifact(
        db_session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        artifact_id=artifact.id,
    )
    assert fetched.id == artifact.id


async def test_artifact_not_readable_from_other_workspace(db_session):
    workspace, trail = await _seed_workspace_trail(db_session)
    other_workspace, other_trail = await _seed_workspace_trail(db_session)

    envelope = validate_artifact_payload(_worked_example_payload())
    artifact = await create_artifact(
        db_session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=None,
        envelope=envelope,
    )

    listed = await list_artifacts(
        db_session, workspace_id=other_workspace.id, trail_id=other_trail.id
    )
    assert listed == []

    with pytest.raises(LookupError):
        await get_artifact(
            db_session,
            workspace_id=other_workspace.id,
            trail_id=other_trail.id,
            artifact_id=artifact.id,
        )


async def test_list_artifacts_filters_by_concept(db_session):
    workspace, trail = await _seed_workspace_trail(db_session)
    concept = await _seed_concept(db_session, trail)

    trail_level = await create_artifact(
        db_session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=None,
        envelope=validate_artifact_payload(_worked_example_payload()),
    )
    concept_level = await create_artifact(
        db_session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        envelope=validate_artifact_payload(_comparison_card_payload()),
    )

    scoped = await list_artifacts(
        db_session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
    )
    assert [a.id for a in scoped] == [concept_level.id]

    all_artifacts = await list_artifacts(db_session, workspace_id=workspace.id, trail_id=trail.id)
    assert {a.id for a in all_artifacts} == {trail_level.id, concept_level.id}


# ---------------------------------------------------------------------------
# Comparison card validation
# ---------------------------------------------------------------------------


async def test_comparison_card_validates():
    envelope = validate_artifact_payload(_comparison_card_payload())
    assert envelope.kind == "comparison_card"
    assert envelope.data.items == ["list", "tuple"]


async def test_comparison_card_mismatched_values_length_rejected():
    payload = _comparison_card_payload(
        data={
            "items": ["list", "tuple"],
            "criteria": [{"label": "Mutable", "values": ["yes"]}],
        }
    )
    with pytest.raises(ValidationError):
        validate_artifact_payload(payload)


# ---------------------------------------------------------------------------
# Timeline validation
# ---------------------------------------------------------------------------


async def test_timeline_validates():
    envelope = validate_artifact_payload(_timeline_payload())
    assert envelope.kind == "timeline"
    assert [e.when for e in envelope.data.events] == ["1957", "1969"]


async def test_timeline_empty_events_rejected():
    with pytest.raises(ValidationError):
        validate_artifact_payload(_timeline_payload(data={"events": []}))


async def test_timeline_malformed_event_rejected():
    payload = _timeline_payload(data={"events": [{"label": "missing when"}]})
    with pytest.raises(ValidationError):
        validate_artifact_payload(payload)


async def test_timeline_requires_text_fallback():
    payload = _timeline_payload()
    del payload["text_fallback"]
    with pytest.raises(ValidationError):
        validate_artifact_payload(payload)


# ---------------------------------------------------------------------------
# Mini graph validation
# ---------------------------------------------------------------------------


async def test_mini_graph_validates():
    envelope = validate_artifact_payload(_mini_graph_payload())
    assert envelope.kind == "mini_graph"
    assert len(envelope.data.nodes) == 3
    assert len(envelope.data.edges) == 2


async def test_mini_graph_too_many_nodes_rejected():
    nodes = [{"id": str(i), "label": f"n{i}"} for i in range(21)]
    payload = _mini_graph_payload(data={"nodes": nodes, "edges": []})
    with pytest.raises(ValidationError):
        validate_artifact_payload(payload)


async def test_mini_graph_edge_to_unknown_node_rejected():
    payload = _mini_graph_payload(
        data={
            "nodes": [{"id": "a", "label": "A"}],
            "edges": [{"source": "a", "target": "missing", "label": None}],
        }
    )
    with pytest.raises(ValidationError):
        validate_artifact_payload(payload)


async def test_mini_graph_malformed_node_rejected():
    payload = _mini_graph_payload(data={"nodes": [{"id": "a"}], "edges": []})
    with pytest.raises(ValidationError):
        validate_artifact_payload(payload)


async def test_mini_graph_requires_text_fallback():
    with pytest.raises(ValidationError):
        validate_artifact_payload(_mini_graph_payload(text_fallback="   "))


# ---------------------------------------------------------------------------
# simulation_slider validation + backend precompute oracle
# ---------------------------------------------------------------------------


def _expected_linear_points(m: float, b: float, x_min: float, x_max: float):
    from backend.app.services.simulations import precompute_simulation

    return precompute_simulation("linear", {"m": m, "b": b}, x_min=x_min, x_max=x_max)


async def test_simulation_slider_validates_and_precomputes():
    envelope = validate_artifact_payload(_simulation_slider_payload())
    assert envelope.kind == "simulation_slider"
    assert envelope.data.sim_kind == "linear"
    # The backend owns + fills ``precomputed`` from the trusted function.
    assert envelope.data.precomputed is not None
    expected = _expected_linear_points(2, 1, 0, 10)
    points = [(p.x, p.y) for p in envelope.data.precomputed.at_defaults]
    assert points == [(p["x"], p["y"]) for p in expected["at_defaults"]]
    assert envelope.data.precomputed.y_bounds.min == expected["y_bounds"]["min"]
    assert envelope.data.precomputed.y_bounds.max == expected["y_bounds"]["max"]


async def test_simulation_slider_overwrites_model_supplied_precomputed():
    payload = _simulation_slider_payload()
    # The model tries to supply a bogus oracle; the backend must overwrite it.
    payload["data"]["precomputed"] = {
        "at_defaults": [{"x": 0, "y": 999}],
        "y_bounds": {"min": 999, "max": 999},
    }
    envelope = validate_artifact_payload(payload)
    expected = _expected_linear_points(2, 1, 0, 10)
    assert len(envelope.data.precomputed.at_defaults) == len(expected["at_defaults"])
    assert envelope.data.precomputed.y_bounds.max != 999


async def test_simulation_slider_unknown_sim_kind_rejected():
    payload = _simulation_slider_payload(
        data={
            "sim_kind": "mystery",
            "parameters": [
                {"name": "m", "label": "Slope", "min": -5, "max": 5, "default": 1},
            ],
            "x_label": "x",
            "y_label": "y",
            "prompt": "?",
        }
    )
    with pytest.raises(ValidationError):
        validate_artifact_payload(payload)


async def test_simulation_slider_wrong_param_names_rejected():
    payload = _simulation_slider_payload(
        data={
            "sim_kind": "linear",
            "parameters": [
                {"name": "slope", "label": "Slope", "min": -5, "max": 5, "default": 1},
                {"name": "b", "label": "Intercept", "min": -10, "max": 10, "default": 0},
            ],
            "x_label": "x",
            "y_label": "y",
            "prompt": "?",
        }
    )
    with pytest.raises(ValidationError):
        validate_artifact_payload(payload)


async def test_simulation_slider_too_many_params_rejected():
    payload = _simulation_slider_payload(
        data={
            "sim_kind": "quadratic",
            "parameters": [
                {"name": "a", "label": "a", "min": -5, "max": 5, "default": 1},
                {"name": "b", "label": "b", "min": -5, "max": 5, "default": 1},
                {"name": "c", "label": "c", "min": -5, "max": 5, "default": 1},
                {"name": "d", "label": "d", "min": -5, "max": 5, "default": 1},
            ],
            "x_label": "x",
            "y_label": "y",
            "prompt": "?",
        }
    )
    with pytest.raises(ValidationError):
        validate_artifact_payload(payload)


async def test_simulation_slider_nan_default_rejected():
    payload = _simulation_slider_payload()
    payload["data"]["parameters"][0]["default"] = float("nan")
    with pytest.raises(ValidationError):
        validate_artifact_payload(payload)


async def test_simulation_slider_inf_bound_rejected():
    payload = _simulation_slider_payload()
    payload["data"]["parameters"][0]["max"] = float("inf")
    with pytest.raises(ValidationError):
        validate_artifact_payload(payload)


async def test_simulation_slider_default_out_of_range_rejected():
    payload = _simulation_slider_payload()
    payload["data"]["parameters"][0]["default"] = 99
    with pytest.raises(ValidationError):
        validate_artifact_payload(payload)


async def test_simulation_slider_unbounded_y_rejected():
    # A steep exponential rate makes the derived y blow up over the x_range.
    payload = _simulation_slider_payload(
        data={
            "sim_kind": "exponential",
            "parameters": [
                {"name": "a", "label": "Scale", "min": 0, "max": 10, "default": 1},
                {"name": "k", "label": "Rate", "min": 0, "max": 20, "default": 10},
            ],
            "x_label": "x",
            "y_label": "y",
            "x_range": {"min": 0, "max": 10},
            "prompt": "?",
        }
    )
    with pytest.raises(ValueError):
        validate_artifact_payload(payload)


async def test_simulation_slider_round_trips(db_session):
    workspace, trail = await _seed_workspace_trail(db_session)
    envelope = validate_artifact_payload(_simulation_slider_payload())
    artifact = await create_artifact(
        db_session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=None,
        envelope=envelope,
    )
    assert artifact.artifact_type == "simulation_slider"
    assert artifact.payload_json["data"]["precomputed"]["at_defaults"]


# ---------------------------------------------------------------------------
# text_fallback + artifact_version validation
# ---------------------------------------------------------------------------


async def test_missing_text_fallback_rejected():
    payload = _worked_example_payload()
    del payload["text_fallback"]
    with pytest.raises(ValidationError):
        validate_artifact_payload(payload)


async def test_empty_text_fallback_rejected():
    with pytest.raises(ValidationError):
        validate_artifact_payload(_worked_example_payload(text_fallback="   "))


async def test_wrong_artifact_version_rejected():
    with pytest.raises(ValidationError):
        validate_artifact_payload(_worked_example_payload(artifact_version=2))


# ---------------------------------------------------------------------------
# Citation dropping
# ---------------------------------------------------------------------------


async def test_disallowed_citation_is_dropped():
    kept_rev = str(uuid.uuid4())
    dropped_rev = str(uuid.uuid4())
    payload = _worked_example_payload(
        provenance={
            "source_ids": [],
            "visibility": "source_derived",
            "citations": [
                {"source_revision_id": kept_rev, "quote": "keep"},
                {"source_revision_id": dropped_rev, "quote": "drop"},
            ],
        }
    )
    envelope = validate_artifact_payload(payload, allowed_revision_ids={kept_rev})
    assert [c.source_revision_id for c in envelope.provenance.citations] == [kept_rev]


async def test_citations_kept_when_no_allow_set():
    rev = str(uuid.uuid4())
    payload = _worked_example_payload(
        provenance={
            "source_ids": [],
            "visibility": "source_derived",
            "citations": [{"source_revision_id": rev}],
        }
    )
    envelope = validate_artifact_payload(payload)
    assert [c.source_revision_id for c in envelope.provenance.citations] == [rev]


# ---------------------------------------------------------------------------
# Export gating
# ---------------------------------------------------------------------------


async def test_local_only_artifact_excluded_from_public_export(db_session):
    workspace, trail = await _seed_workspace_trail(db_session)
    concept = await _seed_concept(db_session, trail)
    artifact = await create_artifact(
        db_session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=concept.id,
        envelope=validate_artifact_payload(_worked_example_payload()),
    )
    assert await can_include_artifact_in_public_export(db_session, artifact) is False


async def test_source_derived_all_public_included(db_session):
    workspace, trail = await _seed_workspace_trail(db_session)
    revision = await _seed_source_with_revision(
        db_session, workspace_id=workspace.id, origin="research_agent", access="public"
    )
    payload = _worked_example_payload(
        provenance={
            "source_ids": [],
            "visibility": "source_derived",
            "citations": [{"source_revision_id": str(revision.id)}],
        }
    )
    artifact = await create_artifact(
        db_session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=None,
        envelope=validate_artifact_payload(payload),
    )
    assert await can_include_artifact_in_public_export(db_session, artifact) is True


async def test_source_derived_with_user_upload_excluded(db_session):
    workspace, trail = await _seed_workspace_trail(db_session)
    public_rev = await _seed_source_with_revision(
        db_session, workspace_id=workspace.id, origin="research_agent", access="public"
    )
    upload_rev = await _seed_source_with_revision(
        db_session,
        workspace_id=workspace.id,
        origin="user_upload",
        access="private",
        include_on_public_export=False,
    )
    payload = _worked_example_payload(
        provenance={
            "source_ids": [],
            "visibility": "source_derived",
            "citations": [
                {"source_revision_id": str(public_rev.id)},
                {"source_revision_id": str(upload_rev.id)},
            ],
        }
    )
    artifact = await create_artifact(
        db_session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=None,
        envelope=validate_artifact_payload(payload),
    )
    assert await can_include_artifact_in_public_export(db_session, artifact) is False


async def test_source_derived_with_non_public_source_excluded(db_session):
    workspace, trail = await _seed_workspace_trail(db_session)
    non_public_rev = await _seed_source_with_revision(
        db_session,
        workspace_id=workspace.id,
        origin="research_agent",
        access="public",
        include_on_public_export=False,
    )
    payload = _worked_example_payload(
        provenance={
            "source_ids": [],
            "visibility": "source_derived",
            "citations": [{"source_revision_id": str(non_public_rev.id)}],
        }
    )
    artifact = await create_artifact(
        db_session,
        workspace_id=workspace.id,
        trail_id=trail.id,
        concept_id=None,
        envelope=validate_artifact_payload(payload),
    )
    assert await can_include_artifact_in_public_export(db_session, artifact) is False
