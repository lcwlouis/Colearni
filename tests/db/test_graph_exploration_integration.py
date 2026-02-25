from __future__ import annotations

from uuid import uuid4

import pytest
from adapters.db.dependencies import get_db_session
from apps.api.main import create_app
from core.settings import get_settings
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


@pytest.fixture
def harness() -> tuple[Session, TestClient]:
    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        conn = engine.connect()
    except SQLAlchemyError as exc:
        engine.dispose()
        pytest.skip(f"Postgres unavailable: {exc}")
    tx, db = conn.begin(), Session(bind=conn)
    app = create_app(settings=settings.model_copy(update={"ingest_build_graph": False}))

    def override_db():
        yield db

    app.dependency_overrides[get_db_session] = override_db
    client = TestClient(app)
    try:
        yield db, client
    finally:
        app.dependency_overrides.clear()
        client.close()
        db.close()
        tx.rollback()
        conn.close()
        engine.dispose()


def _i(db: Session, sql: str, **params: object) -> int:
    return int(db.execute(text(sql), params).scalar_one())


def _ws(db: Session, label: str) -> int:
    suffix = uuid4().hex
    user_id = _i(
        db,
        "INSERT INTO users (email) VALUES (:email) RETURNING id",
        email=f"{label}-{suffix}@example.test",
    )
    return _i(
        db,
        "INSERT INTO workspaces (name, owner_user_id) VALUES (:name, :owner_user_id) RETURNING id",
        name=f"{label}-{suffix}",
        owner_user_id=user_id,
    )


def _c(db: Session, workspace_id: int, name: str) -> int:
    return _i(
        db,
        "INSERT INTO concepts_canon ("
        "workspace_id, canonical_name, description, aliases, is_active, dirty) "
        "VALUES (:workspace_id,:canonical_name,:description,:aliases,TRUE,FALSE) "
        "RETURNING id",
        workspace_id=workspace_id,
        canonical_name=name,
        description=f"Description: {name}",
        aliases=[name],
    )


def _e(db: Session, workspace_id: int, src_id: int, tgt_id: int, weight: float) -> None:
    db.execute(
        text(
            "INSERT INTO edges_canon (workspace_id, src_id, tgt_id, relation_type, description, "
            "keywords, weight) VALUES (:workspace_id,:src_id,:tgt_id,'related_to','',"
            "'{}'::text[],:weight)"
        ),
        {"workspace_id": workspace_id, "src_id": src_id, "tgt_id": tgt_id, "weight": weight},
    )


def test_subgraph_workspace_scoped_and_bounded(harness: tuple[Session, TestClient]) -> None:
    db, client = harness
    ws1, ws2 = _ws(db, "graph-subgraph-a"), _ws(db, "graph-subgraph-b")
    seed, a, b = _c(db, ws1, "Seed Topic"), _c(db, ws1, "Alpha"), _c(db, ws1, "beta")
    g, d = _c(db, ws1, "Gamma"), _c(db, ws1, "Delta")
    for src, tgt, wt in [(seed, a, 9.0), (seed, b, 7.0), (a, g, 5.0), (b, d, 3.0)]:
        _e(db, ws1, src, tgt, wt)
    _e(db, ws2, _c(db, ws2, "Foreign A"), _c(db, ws2, "Foreign B"), 10.0)

    wrong = client.get(f"/graph/concepts/{seed}/subgraph", params={"workspace_id": ws2})
    assert wrong.status_code == 404
    detail = client.get(f"/graph/concepts/{seed}", params={"workspace_id": ws1}).json()
    assert detail["concept"]["degree"] == 2
    payload = client.get(
        f"/graph/concepts/{seed}/subgraph",
        params={"workspace_id": ws1, "max_hops": 2, "max_nodes": 3, "max_edges": 2},
    ).json()
    assert [n["concept_id"] for n in payload["nodes"]] == [seed, a, b]
    assert [e["weight"] for e in payload["edges"]] == [9.0, 7.0]
    assert client.get(
        f"/graph/concepts/{seed}/subgraph", params={"workspace_id": ws1, "max_hops": 4}
    ).status_code == 422


def test_lucky_adjacent_picks_top_ranked_candidate(harness: tuple[Session, TestClient]) -> None:
    db, client = harness
    ws = _ws(db, "graph-lucky-adjacent")
    seed = _c(db, ws, "Seed")
    a, b, hop = _c(db, ws, "Candidate A"), _c(db, ws, "Candidate B"), _c(db, ws, "Hop Two")
    _e(db, ws, seed, a, 4.0)
    _e(db, ws, seed, b, 8.0)
    _e(db, ws, a, hop, 10.0)
    pick = client.get(
        "/graph/lucky",
        params={"workspace_id": ws, "concept_id": seed, "mode": "adjacent", "k_hops": 2},
    ).json()["pick"]
    assert pick["concept_id"] == b
    assert pick["hop_distance"] == 1
    assert pick["score_components"]["strongest_link_weight"] == 8.0


def test_lucky_wildcard_excludes_khop_and_picks_relevant_candidate(
    harness: tuple[Session, TestClient],
) -> None:
    db, client = harness
    ws = _ws(db, "graph-lucky-wildcard")
    seed = _c(db, ws, "Seed")
    near, small = _c(db, ws, "Near"), _c(db, ws, "Outside Small")
    wild, p1, p2 = _c(db, ws, "Wildcard"), _c(db, ws, "Peer A"), _c(db, ws, "Peer B")
    _e(db, ws, seed, near, 5.0)
    _e(db, ws, near, small, 4.0)
    _e(db, ws, wild, p1, 7.0)
    _e(db, ws, wild, p2, 6.0)
    pick = client.get(
        "/graph/lucky",
        params={"workspace_id": ws, "concept_id": seed, "mode": "wildcard", "k_hops": 1},
    ).json()["pick"]
    assert pick["concept_id"] == wild
    assert pick["hop_distance"] is None
    assert pick["score_components"] == {"degree": 2, "total_incident_weight": 13.0}


def test_lucky_returns_404_when_no_candidate(harness: tuple[Session, TestClient]) -> None:
    db, client = harness
    ws = _ws(db, "graph-lucky-empty")
    seed, near, far = _c(db, ws, "Seed"), _c(db, ws, "Near"), _c(db, ws, "Far")
    _e(db, ws, seed, near, 1.0)
    _e(db, ws, near, far, 1.0)
    response = client.get(
        "/graph/lucky",
        params={"workspace_id": ws, "concept_id": seed, "mode": "wildcard", "k_hops": 3},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "No wildcard candidate found."
