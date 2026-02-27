from __future__ import annotations

from uuid import uuid4

import pytest
from adapters.db.auth import UserRow
from adapters.db.dependencies import get_db_session
from apps.api.dependencies import get_current_user
from apps.api.main import create_app
from core.settings import get_settings
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


@pytest.fixture
def harness() -> tuple[Session, TestClient, int]:
    """Yield (db, client, user_id) with auth overridden."""
    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        conn = engine.connect()
    except SQLAlchemyError as exc:
        engine.dispose()
        pytest.skip(f"Postgres unavailable: {exc}")
    tx, db = conn.begin(), Session(bind=conn)
    app = create_app(settings=settings.model_copy(update={"ingest_build_graph": False}))

    # Create a shared test user
    suffix = uuid4().hex[:8]
    user_row = (
        db.execute(
            text("INSERT INTO users (email) VALUES (:email) RETURNING id, public_id"),
            {"email": f"graph-test-{suffix}@example.test"},
        )
        .mappings()
        .one()
    )
    user_id = int(user_row["id"])
    mock_user = UserRow(
        id=user_id,
        public_id=str(user_row["public_id"]),
        email=f"graph-test-{suffix}@example.test",
        display_name=None,
    )

    def override_db():
        yield db

    def override_user():
        return mock_user

    app.dependency_overrides[get_db_session] = override_db
    app.dependency_overrides[get_current_user] = override_user
    client = TestClient(app)
    try:
        yield db, client, user_id
    finally:
        app.dependency_overrides.clear()
        client.close()
        db.close()
        tx.rollback()
        conn.close()
        engine.dispose()


def _i(db: Session, sql: str, **params: object) -> int:
    return int(db.execute(text(sql), params).scalar_one())


def _ws(db: Session, label: str, user_id: int) -> tuple[int, str]:
    """Create workspace + membership, return (internal_id, public_id)."""
    suffix = uuid4().hex
    row = (
        db.execute(
            text(
                "INSERT INTO workspaces (name, owner_user_id) "
                "VALUES (:name, :owner_user_id) RETURNING id, public_id"
            ),
            {"name": f"{label}-{suffix}", "owner_user_id": user_id},
        )
        .mappings()
        .one()
    )
    wid, pid = int(row["id"]), str(row["public_id"])
    db.execute(
        text(
            "INSERT INTO workspace_members (workspace_id, user_id, role) "
            "VALUES (:wid, :uid, 'owner')"
        ),
        {"wid": wid, "uid": user_id},
    )
    return wid, pid


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


def test_subgraph_workspace_scoped_and_bounded(harness: tuple[Session, TestClient, int]) -> None:
    db, client, user_id = harness
    ws1_id, ws1_pid = _ws(db, "graph-subgraph-a", user_id)
    ws2_id, ws2_pid = _ws(db, "graph-subgraph-b", user_id)
    seed, a, b = _c(db, ws1_id, "Seed Topic"), _c(db, ws1_id, "Alpha"), _c(db, ws1_id, "beta")
    g, d = _c(db, ws1_id, "Gamma"), _c(db, ws1_id, "Delta")
    for src, tgt, wt in [(seed, a, 9.0), (seed, b, 7.0), (a, g, 5.0), (b, d, 3.0)]:
        _e(db, ws1_id, src, tgt, wt)
    _e(db, ws2_id, _c(db, ws2_id, "Foreign A"), _c(db, ws2_id, "Foreign B"), 10.0)

    wrong = client.get(f"/workspaces/{ws2_pid}/graph/concepts/{seed}/subgraph")
    assert wrong.status_code == 404
    detail = client.get(f"/workspaces/{ws1_pid}/graph/concepts/{seed}").json()
    assert detail["concept"]["degree"] == 2
    payload = client.get(
        f"/workspaces/{ws1_pid}/graph/concepts/{seed}/subgraph",
        params={"max_hops": 2, "max_nodes": 3, "max_edges": 2},
    ).json()
    assert [n["concept_id"] for n in payload["nodes"]] == [seed, a, b]
    assert [e["weight"] for e in payload["edges"]] == [9.0, 7.0]
    assert client.get(
        f"/workspaces/{ws1_pid}/graph/concepts/{seed}/subgraph", params={"max_hops": 4}
    ).status_code == 422


def test_lucky_adjacent_picks_top_ranked_candidate(harness: tuple[Session, TestClient, int]) -> None:
    db, client, user_id = harness
    ws_id, ws_pid = _ws(db, "graph-lucky-adjacent", user_id)
    seed = _c(db, ws_id, "Seed")
    a, b, hop = _c(db, ws_id, "Candidate A"), _c(db, ws_id, "Candidate B"), _c(db, ws_id, "Hop Two")
    _e(db, ws_id, seed, a, 4.0)
    _e(db, ws_id, seed, b, 8.0)
    _e(db, ws_id, a, hop, 10.0)
    pick = client.get(
        f"/workspaces/{ws_pid}/graph/lucky",
        params={"concept_id": seed, "mode": "adjacent", "k_hops": 2},
    ).json()["pick"]
    assert pick["concept_id"] == b
    assert pick["hop_distance"] == 1
    assert pick["score_components"]["strongest_link_weight"] == 8.0


def test_lucky_wildcard_excludes_khop_and_picks_relevant_candidate(
    harness: tuple[Session, TestClient, int],
) -> None:
    db, client, user_id = harness
    ws_id, ws_pid = _ws(db, "graph-lucky-wildcard", user_id)
    seed = _c(db, ws_id, "Seed")
    near, small = _c(db, ws_id, "Near"), _c(db, ws_id, "Outside Small")
    wild, p1, p2 = _c(db, ws_id, "Wildcard"), _c(db, ws_id, "Peer A"), _c(db, ws_id, "Peer B")
    _e(db, ws_id, seed, near, 5.0)
    _e(db, ws_id, near, small, 4.0)
    _e(db, ws_id, wild, p1, 7.0)
    _e(db, ws_id, wild, p2, 6.0)
    pick = client.get(
        f"/workspaces/{ws_pid}/graph/lucky",
        params={"concept_id": seed, "mode": "wildcard", "k_hops": 1},
    ).json()["pick"]
    assert pick["concept_id"] == wild
    assert pick["hop_distance"] is None
    assert pick["score_components"] == {"degree": 2, "total_incident_weight": 13.0}


def test_lucky_returns_404_when_no_candidate(harness: tuple[Session, TestClient, int]) -> None:
    db, client, user_id = harness
    ws_id, ws_pid = _ws(db, "graph-lucky-empty", user_id)
    seed, near, far = _c(db, ws_id, "Seed"), _c(db, ws_id, "Near"), _c(db, ws_id, "Far")
    _e(db, ws_id, seed, near, 1.0)
    _e(db, ws_id, near, far, 1.0)
    response = client.get(
        f"/workspaces/{ws_pid}/graph/lucky",
        params={"concept_id": seed, "mode": "wildcard", "k_hops": 3},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "No wildcard candidate found."
