from __future__ import annotations

import uuid

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.artifact import Artifact
from backend.app.models.source import SourceRecord, SourceRevision
from backend.app.schemas.artifact import (
    ArtifactEnvelopeOutput,
    SimulationPrecomputed,
    SimulationSliderEnvelope,
)
from backend.app.services.simulations import (
    DEFAULT_SIM_X_MAX,
    DEFAULT_SIM_X_MIN,
    precompute_simulation,
)
from backend.app.services.trail_pack_export import _can_include_source_in_public_export

# Parses + validates the strict discriminated envelope. Reused across calls.
_envelope_adapter: TypeAdapter[ArtifactEnvelopeOutput] = TypeAdapter(ArtifactEnvelopeOutput)


def validate_artifact_payload(
    raw: dict,
    *,
    allowed_revision_ids: set[str] | None = None,
) -> ArtifactEnvelopeOutput:
    """Parse + validate a raw artifact payload against the strict envelope.

    When ``allowed_revision_ids`` is provided, any citation whose
    ``source_revision_id`` is not in that set is DROPPED (generation passes the
    real retrieved revision ids here). When not provided, all citations are kept.
    """
    envelope = _envelope_adapter.validate_python(raw)
    if allowed_revision_ids is not None:
        envelope.provenance.citations = [
            citation
            for citation in envelope.provenance.citations
            if citation.source_revision_id in allowed_revision_ids
        ]
    if isinstance(envelope, SimulationSliderEnvelope):
        # Backend owns the simulation oracle: (re)compute ``precomputed`` from
        # the trusted hardcoded functions, overwriting anything the model
        # emitted. Raises ValueError on non-finite/unbounded derived y.
        _apply_simulation_precompute(envelope)
    return envelope


def _apply_simulation_precompute(envelope: SimulationSliderEnvelope) -> None:
    data = envelope.data
    coefficients = {param.name: param.default for param in data.parameters}
    x_min = data.x_range.min if data.x_range is not None else DEFAULT_SIM_X_MIN
    x_max = data.x_range.max if data.x_range is not None else DEFAULT_SIM_X_MAX
    result = precompute_simulation(
        data.sim_kind,
        coefficients,
        x_min=x_min,
        x_max=x_max,
    )
    data.precomputed = SimulationPrecomputed.model_validate(result)


async def create_artifact(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID | None,
    envelope: ArtifactEnvelopeOutput,
) -> Artifact:
    """Persist a validated artifact envelope.

    NOTE: advisory-lock single-flight dedupe (mirroring ``quiz_drafts``) lands
    with the artifact-builder sub-agent increment; the read/create foundation
    here does not need it yet.
    """
    source_refs = list(
        dict.fromkeys(citation.source_revision_id for citation in envelope.provenance.citations)
    )
    artifact = Artifact(
        workspace_id=workspace_id,
        trail_id=trail_id,
        concept_id=concept_id,
        artifact_type=envelope.kind,
        title=envelope.title,
        payload_json=envelope.model_dump(mode="json"),
        source_refs_json=source_refs,
        visibility=envelope.provenance.visibility,
    )
    session.add(artifact)
    await session.commit()
    await session.refresh(artifact)
    return artifact


async def list_artifacts(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    concept_id: uuid.UUID | None = None,
) -> list[Artifact]:
    stmt = (
        select(Artifact)
        .where(Artifact.workspace_id == workspace_id, Artifact.trail_id == trail_id)
        .order_by(Artifact.created_at)
    )
    if concept_id is not None:
        stmt = stmt.where(Artifact.concept_id == concept_id)
    return list(await session.scalars(stmt))


async def get_artifact(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> Artifact:
    artifact = await session.scalar(
        select(Artifact).where(
            Artifact.id == artifact_id,
            Artifact.workspace_id == workspace_id,
            Artifact.trail_id == trail_id,
        )
    )
    if artifact is None:
        raise LookupError("Artifact not found")
    return artifact


async def can_include_artifact_in_public_export(
    session: AsyncSession,
    artifact: Artifact,
) -> bool:
    """Whether an artifact may appear in a PUBLIC Trail Pack export.

    Concept-level / ``local_only`` artifacts stay local-only (like the primer)
    and are excluded. ``source_derived`` artifacts are included only if EVERY
    contributing source passes the existing source-level export gate AND none is
    a ``user_upload`` (all-or-nothing). Reuses ``_can_include_source_in_public_export``.
    """
    if artifact.visibility != "source_derived":
        return False

    try:
        revision_ids = {uuid.UUID(ref) for ref in (artifact.source_refs_json or [])}
    except (ValueError, TypeError):
        return False
    if not revision_ids:
        return False

    revisions = list(
        await session.scalars(
            select(SourceRevision).where(
                SourceRevision.id.in_(revision_ids),
                SourceRevision.workspace_id == artifact.workspace_id,
            )
        )
    )
    # Every cited revision must resolve in-workspace; otherwise we can't verify.
    if len(revisions) != len(revision_ids):
        return False

    source_ids = {revision.source_id for revision in revisions}
    sources = list(
        await session.scalars(
            select(SourceRecord).where(
                SourceRecord.id.in_(source_ids),
                SourceRecord.workspace_id == artifact.workspace_id,
            )
        )
    )
    if len(sources) != len(source_ids):
        return False

    for source in sources:
        if source.origin == "user_upload":
            return False
        if not _can_include_source_in_public_export(source):
            return False
    return True
