"""Graph exploration routes (workspace-scoped)."""

from __future__ import annotations

from typing import Literal

from adapters.db.dependencies import get_db_session
from adapters.llm.factory import build_graph_llm_client
from apps.api.dependencies import WorkspaceContext, get_workspace_context
from core.schemas import (
    GardenerRunResponse,
    GraphConceptDetailResponse,
    GraphConceptListResponse,
    GraphLuckyResponse,
    GraphSubgraphResponse,
)
from core.settings import Settings
from domain.graph.explore import (
    MAX_EDGES_CAP,
    MAX_HOPS_CAP,
    MAX_NODES_CAP,
    GraphNotFoundError,
    LuckyNoCandidateError,
    get_bounded_subgraph,
    get_concept_detail,
    get_full_subgraph,
    list_concepts,
    pick_lucky,
)
from domain.graph.gardener import run_graph_gardener
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session

router = APIRouter(prefix="/workspaces/{ws_id}/graph", tags=["graph"])


def _not_found(exc: Exception) -> None:
    raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/concepts/{concept_id}", response_model=GraphConceptDetailResponse)
def concept_detail(
    concept_id: int = Path(gt=0),
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> GraphConceptDetailResponse:
    try:
        return GraphConceptDetailResponse.model_validate(
            get_concept_detail(db, workspace_id=ws.workspace_id, concept_id=concept_id)
        )
    except GraphNotFoundError as exc:
        _not_found(exc)


@router.get("/concepts", response_model=GraphConceptListResponse)
def concepts(
    q: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> GraphConceptListResponse:
    return GraphConceptListResponse.model_validate(
        list_concepts(
            db,
            workspace_id=ws.workspace_id,
            user_id=ws.user.id,
            q=q,
            limit=limit,
        )
    )


@router.get("/full", response_model=GraphSubgraphResponse)
def full_graph(
    max_nodes: int = Query(default=100, ge=1, le=500),
    max_edges: int = Query(default=300, ge=1, le=1000),
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> GraphSubgraphResponse:
    return GraphSubgraphResponse.model_validate(
        get_full_subgraph(
            db,
            workspace_id=ws.workspace_id,
            max_nodes=max_nodes,
            max_edges=max_edges,
            user_id=ws.user.id,
        )
    )


@router.get("/concepts/{concept_id}/subgraph", response_model=GraphSubgraphResponse)
def concept_subgraph(
    concept_id: int = Path(gt=0),
    max_hops: int = Query(default=1, ge=1, le=MAX_HOPS_CAP),
    max_nodes: int = Query(default=40, ge=1, le=MAX_NODES_CAP),
    max_edges: int = Query(default=80, ge=1, le=MAX_EDGES_CAP),
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> GraphSubgraphResponse:
    try:
        return GraphSubgraphResponse.model_validate(
            get_bounded_subgraph(
                db,
                workspace_id=ws.workspace_id,
                concept_id=concept_id,
                max_hops=max_hops,
                max_nodes=max_nodes,
                max_edges=max_edges,
                user_id=ws.user.id,
            )
        )
    except GraphNotFoundError as exc:
        _not_found(exc)


@router.get("/lucky", response_model=GraphLuckyResponse)
def lucky_pick(
    concept_id: int = Query(gt=0),
    mode: Literal["adjacent", "wildcard"] = Query(),
    k_hops: int = Query(default=1, ge=1, le=MAX_HOPS_CAP),
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> GraphLuckyResponse:
    try:
        return GraphLuckyResponse.model_validate(
            pick_lucky(
                db, workspace_id=ws.workspace_id, concept_id=concept_id, mode=mode, k_hops=k_hops
            )
        )
    except (GraphNotFoundError, LuckyNoCandidateError) as exc:
        _not_found(exc)


@router.post("/gardener/run", response_model=GardenerRunResponse)
def run_gardener(
    request: Request,
    full_scan: bool = Query(default=True),
    ws: WorkspaceContext = Depends(get_workspace_context),
    db: Session = Depends(get_db_session),
) -> GardenerRunResponse:
    settings_state = getattr(request.app.state, "settings", None)
    settings = settings_state if isinstance(settings_state, Settings) else Settings()
    llm_client = build_graph_llm_client(
        settings=settings,
        timeout_override=settings.graph_llm_long_timeout_seconds,
    )
    result = run_graph_gardener(
        db,
        workspace_id=ws.workspace_id,
        llm_client=llm_client,
        settings=settings,
        full_scan=full_scan,
    )
    return GardenerRunResponse(
        merges_applied=result.merges_applied,
        links_created=result.links_created,
        clusters_processed=result.clusters_processed,
        llm_calls=result.llm_calls,
        pruned_concepts=result.pruned_concepts,
        pruned_edges=result.pruned_edges,
        tiers_backfilled=result.tiers_backfilled,
    )
