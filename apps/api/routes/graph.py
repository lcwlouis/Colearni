from __future__ import annotations

from typing import Literal

from adapters.db.dependencies import get_db_session
from core.schemas import (
    GraphConceptDetailResponse,
    GraphConceptListResponse,
    GraphLuckyResponse,
    GraphSubgraphResponse,
)
from domain.graph.explore import (
    MAX_EDGES_CAP,
    MAX_HOPS_CAP,
    MAX_NODES_CAP,
    GraphNotFoundError,
    LuckyNoCandidateError,
    get_bounded_subgraph,
    get_concept_detail,
    list_concepts,
    pick_lucky,
)
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

router = APIRouter(prefix="/graph", tags=["graph"])


def _not_found(exc: Exception) -> None:
    raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/concepts/{concept_id}", response_model=GraphConceptDetailResponse)
def concept_detail(
    concept_id: int = Path(gt=0),
    workspace_id: int = Query(gt=0),
    db: Session = Depends(get_db_session),
) -> GraphConceptDetailResponse:
    try:
        return GraphConceptDetailResponse.model_validate(
            get_concept_detail(db, workspace_id=workspace_id, concept_id=concept_id)
        )
    except GraphNotFoundError as exc:
        _not_found(exc)


@router.get("/concepts", response_model=GraphConceptListResponse)
def concepts(
    workspace_id: int = Query(gt=0),
    user_id: int | None = Query(default=None, gt=0),
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db_session),
) -> GraphConceptListResponse:
    return GraphConceptListResponse.model_validate(
        list_concepts(
            db,
            workspace_id=workspace_id,
            user_id=user_id,
            q=q,
            limit=limit,
        )
    )


@router.get("/concepts/{concept_id}/subgraph", response_model=GraphSubgraphResponse)
def concept_subgraph(
    concept_id: int = Path(gt=0),
    workspace_id: int = Query(gt=0),
    user_id: int | None = Query(default=None, gt=0),
    max_hops: int = Query(default=1, ge=1, le=MAX_HOPS_CAP),
    max_nodes: int = Query(default=40, ge=1, le=MAX_NODES_CAP),
    max_edges: int = Query(default=80, ge=1, le=MAX_EDGES_CAP),
    db: Session = Depends(get_db_session),
) -> GraphSubgraphResponse:
    try:
        return GraphSubgraphResponse.model_validate(
            get_bounded_subgraph(
                db,
                workspace_id=workspace_id,
                concept_id=concept_id,
                max_hops=max_hops,
                max_nodes=max_nodes,
                max_edges=max_edges,
                user_id=user_id,
            )
        )
    except GraphNotFoundError as exc:
        _not_found(exc)


@router.get("/lucky", response_model=GraphLuckyResponse)
def lucky_pick(
    workspace_id: int = Query(gt=0),
    concept_id: int = Query(gt=0),
    mode: Literal["adjacent", "wildcard"] = Query(),
    k_hops: int = Query(default=1, ge=1, le=MAX_HOPS_CAP),
    db: Session = Depends(get_db_session),
) -> GraphLuckyResponse:
    try:
        return GraphLuckyResponse.model_validate(
            pick_lucky(
                db, workspace_id=workspace_id, concept_id=concept_id, mode=mode, k_hops=k_hops
            )
        )
    except (GraphNotFoundError, LuckyNoCandidateError) as exc:
        _not_found(exc)
