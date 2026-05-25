import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.concept import ConceptEdge, ConceptNode
from backend.app.models.trail import Trail
from backend.app.services.mastery import MasteryState, list_mastery_states


@dataclass(frozen=True)
class NextConceptRecommendation:
    concept: ConceptNode | None
    reason: str
    all_mastered: bool
    mastery_status: str | None = None
    concept_level: str | None = None


_ELIGIBLE_STATUSES = frozenset({"not_started", "needs_review"})
_SATISFIED_PREREQUISITE_STATUSES = frozenset({"mastered", "learning"})
_CONCEPT_LEVEL_PRIORITY = {
    "topic": 0,
    "subtopic": 1,
    "umbrella": 2,
    "granular": 3,
}
_DIFFICULTY_PRIORITY = {
    "beginner": 0,
    "intermediate": 1,
    "advanced": 2,
}


def recommend_next_concept(
    *,
    concepts: list[ConceptNode],
    edges: list[ConceptEdge],
    mastery_map: dict[uuid.UUID, MasteryState],
) -> NextConceptRecommendation:
    prerequisite_ids_by_target: dict[uuid.UUID, list[uuid.UUID]] = {}
    for edge in edges:
        if edge.relation_type == "prerequisite":
            prerequisite_ids_by_target.setdefault(edge.target_node_id, []).append(
                edge.source_node_id
            )

    candidates = [
        concept
        for concept in concepts
        if _status_for(concept.id, mastery_map) in _ELIGIBLE_STATUSES
    ]
    if not candidates:
        return NextConceptRecommendation(
            concept=None,
            reason="All concepts mastered. Consider reviewing or exploring adjacent topics.",
            all_mastered=True,
        )

    def sort_key(concept: ConceptNode) -> tuple[int, int, int, int, str]:
        status = _status_for(concept.id, mastery_map)
        prerequisite_ids = prerequisite_ids_by_target.get(concept.id, [])
        prerequisites_satisfied = _prerequisites_satisfied(prerequisite_ids, mastery_map)
        return (
            0 if prerequisites_satisfied else 1,
            0 if status == "needs_review" else 1,
            _CONCEPT_LEVEL_PRIORITY.get(concept.concept_level, 99),
            _DIFFICULTY_PRIORITY.get(concept.difficulty, 99),
            concept.title.lower(),
        )

    winner = min(candidates, key=sort_key)
    prerequisite_ids = prerequisite_ids_by_target.get(winner.id, [])
    prerequisites_satisfied = _prerequisites_satisfied(prerequisite_ids, mastery_map)
    return NextConceptRecommendation(
        concept=winner,
        reason=_recommendation_reason(
            status=_status_for(winner.id, mastery_map),
            difficulty=winner.difficulty,
            prerequisite_ids=prerequisite_ids,
            prerequisites_satisfied=prerequisites_satisfied,
        ),
        all_mastered=False,
        mastery_status=_status_for(winner.id, mastery_map),
        concept_level=winner.concept_level,
    )


async def get_next_concept_for_trail(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    trail_id: uuid.UUID,
) -> NextConceptRecommendation:
    trail = await session.scalar(
        select(Trail).where(Trail.id == trail_id, Trail.workspace_id == workspace_id)
    )
    if trail is None:
        raise LookupError(f"Trail {trail_id} not found")

    concepts = list(
        await session.scalars(
            select(ConceptNode)
            .where(ConceptNode.trail_id == trail_id)
            .order_by(ConceptNode.title, ConceptNode.id)
        )
    )
    if not concepts:
        return NextConceptRecommendation(
            concept=None,
            reason="No concepts in this Trail yet.",
            all_mastered=False,
        )

    edges = list(
        await session.scalars(
            select(ConceptEdge).where(ConceptEdge.trail_id == trail_id).order_by(ConceptEdge.id)
        )
    )
    mastery_map = await list_mastery_states(session, workspace_id=workspace_id, concepts=concepts)
    return recommend_next_concept(concepts=concepts, edges=edges, mastery_map=mastery_map)


def _status_for(concept_id: uuid.UUID, mastery_map: dict[uuid.UUID, MasteryState]) -> str:
    state = mastery_map.get(concept_id)
    if state is None:
        return "not_started"
    return state.status


def _prerequisites_satisfied(
    prerequisite_ids: list[uuid.UUID], mastery_map: dict[uuid.UUID, MasteryState]
) -> bool:
    return all(
        _status_for(prerequisite_id, mastery_map) in _SATISFIED_PREREQUISITE_STATUSES
        for prerequisite_id in prerequisite_ids
    )


def _recommendation_reason(
    *,
    status: str,
    difficulty: str,
    prerequisite_ids: list[uuid.UUID],
    prerequisites_satisfied: bool,
) -> str:
    if status == "needs_review" and not prerequisite_ids:
        return "Needs review - no prerequisites blocking it."
    if status == "needs_review" and prerequisites_satisfied:
        return "Needs review - prerequisites are ready."
    if status == "needs_review" and not prerequisites_satisfied:
        return "Needs review - prerequisites not yet complete."
    if not prerequisites_satisfied:
        return "Prerequisites not yet complete, but this is the best available option."
    if not prerequisite_ids and difficulty == "beginner":
        return "Good starting point - no prerequisites, beginner level."
    if not prerequisite_ids:
        return "Good starting point - no prerequisites."
    return "Prerequisites satisfied - next topic to start."
