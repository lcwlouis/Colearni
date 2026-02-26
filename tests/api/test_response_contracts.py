from __future__ import annotations

from typing import Any

import pytest
from adapters.db.dependencies import get_db_session
from apps.api.main import app
from fastapi.testclient import TestClient


def _override_db() -> Any:
    yield object()

def _schema_ref(spec: dict[str, Any], path: str, method: str, status: str) -> str:
    return str(
        spec["paths"][path][method]["responses"][status]["content"]["application/json"]["schema"][
            "$ref"
        ]
    )

def _patch(monkeypatch: Any, target: str, payload: dict[str, Any]) -> None:
    monkeypatch.setattr(target, lambda *args, **kwargs: payload)

def _quiz_create() -> dict[str, Any]:
    return {
        "quiz_id": 1,
        "workspace_id": 2,
        "user_id": 3,
        "concept_id": 4,
        "status": "ready",
        "items": [
            {
                "item_id": 11,
                "position": 1,
                "item_type": "mcq",
                "prompt": "q",
                "choices": [{"id": "a", "text": "Choice A"}],
            }
        ],
    }


def _submit(with_mastery: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "quiz_id": 1,
        "attempt_id": 9,
        "score": 1.0,
        "passed": True,
        "critical_misconception": False,
        "overall_feedback": "ok",
        "items": [
            {
                "item_id": 11,
                "item_type": "mcq",
                "result": "correct",
                "is_correct": True,
                "critical_misconception": False,
                "feedback": "ok",
                "score": 1.0,
            }
        ],
        "replayed": False,
        "retry_hint": None,
    }
    if with_mastery:
        payload["mastery_status"] = "learned"
        payload["mastery_score"] = 1.0
    return payload


OPENAPI_ROUTES = {
    ("/healthz", "get"),
    ("/chat/respond", "post"),
    ("/documents/upload", "post"),
    ("/graph/concepts/{concept_id}", "get"),
    ("/graph/concepts/{concept_id}/subgraph", "get"),
    ("/graph/lucky", "get"),
    ("/quizzes/level-up", "post"),
    ("/quizzes/{quiz_id}/submit", "post"),
    ("/practice/flashcards", "post"),
    ("/practice/quizzes", "post"),
    ("/practice/quizzes/{quiz_id}/submit", "post"),
}


OPENAPI_REFS = [
    ("/chat/respond", "post", "200", "#/components/schemas/AssistantResponseEnvelope"),
    ("/documents/upload", "post", "201", "#/components/schemas/DocumentUploadResponse"),
    ("/quizzes/level-up", "post", "201", "#/components/schemas/QuizCreateResponse"),
    ("/quizzes/{quiz_id}/submit", "post", "200", "#/components/schemas/LevelUpQuizSubmitResponse"),
    ("/practice/flashcards", "post", "200", "#/components/schemas/PracticeFlashcardsResponse"),
    ("/practice/quizzes", "post", "201", "#/components/schemas/QuizCreateResponse"),
    (
        "/practice/quizzes/{quiz_id}/submit",
        "post",
        "200",
        "#/components/schemas/PracticeQuizSubmitResponse",
    ),
    (
        "/graph/concepts/{concept_id}",
        "get",
        "200",
        "#/components/schemas/GraphConceptDetailResponse",
    ),
    (
        "/graph/concepts/{concept_id}/subgraph",
        "get",
        "200",
        "#/components/schemas/GraphSubgraphResponse",
    ),
    ("/graph/lucky", "get", "200", "#/components/schemas/GraphLuckyResponse"),
]
SUBMIT_FIELDS = {
    "quiz_id",
    "attempt_id",
    "score",
    "passed",
    "critical_misconception",
    "overall_feedback",
    "items",
    "replayed",
    "retry_hint",
}
REQUIRED_FIELDS = {
    "QuizCreateResponse": {"quiz_id", "workspace_id", "user_id", "concept_id", "status", "items"},
    "LevelUpQuizSubmitResponse": SUBMIT_FIELDS | {"mastery_status", "mastery_score"},
    "PracticeFlashcardsResponse": {"workspace_id", "concept_id", "concept_name", "flashcards"},
    "PracticeQuizSubmitResponse": SUBMIT_FIELDS,
    "GraphConceptDetailResponse": {"workspace_id", "concept"},
    "GraphSubgraphResponse": {"workspace_id", "root_concept_id", "max_hops", "nodes", "edges"},
    "GraphLuckyResponse": {"workspace_id", "seed_concept_id", "mode", "pick"},
}


@pytest.mark.parametrize(("path", "method"), sorted(OPENAPI_ROUTES))
def test_openapi_declares_expected_backend_routes(path: str, method: str) -> None:
    assert method in app.openapi()["paths"][path]


@pytest.mark.parametrize(("path", "method", "status", "ref"), OPENAPI_REFS)
def test_openapi_routes_use_typed_response_models(
    path: str,
    method: str,
    status: str,
    ref: str,
) -> None:
    assert _schema_ref(app.openapi(), path, method, status) == ref

def test_openapi_required_fields_cover_contract() -> None:
    schemas = app.openapi()["components"]["schemas"]
    for name, fields in REQUIRED_FIELDS.items():
        assert fields.issubset(set(schemas[name]["required"]))

@pytest.fixture
def client() -> Any:
    app.dependency_overrides[get_db_session] = _override_db
    prev_llm = getattr(app.state, "graph_llm_client", None)
    app.state.graph_llm_client = object()
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        app.state.graph_llm_client = prev_llm
        app.dependency_overrides.clear()

def test_quizzes_runtime_response_contracts(client: Any, monkeypatch: Any) -> None:
    _patch(monkeypatch, "apps.api.routes.quizzes.create_level_up_quiz", _quiz_create())
    _patch(monkeypatch, "apps.api.routes.quizzes.submit_level_up_quiz", _submit(with_mastery=True))
    created = client.post(
        "/quizzes/level-up",
        json={"workspace_id": 2, "user_id": 3, "concept_id": 4, "question_count": 5},
    )
    submitted = client.post(
        "/quizzes/1/submit",
        json={"workspace_id": 2, "user_id": 3, "answers": [{"item_id": 11, "answer": "a"}]},
    )
    assert (created.status_code, submitted.status_code) == (201, 200)
    assert REQUIRED_FIELDS["QuizCreateResponse"] <= set(created.json()) and {
        "mastery_status",
        "mastery_score",
    } <= set(submitted.json())
    item = created.json()["items"][0]
    assert set(item) == {"item_id", "position", "item_type", "prompt", "choices"}
    assert item["choices"] == [{"id": "a", "text": "Choice A"}]

def test_practice_runtime_response_contracts(client: Any, monkeypatch: Any) -> None:
    _patch(
        monkeypatch,
        "apps.api.routes.practice.generate_practice_flashcards",
        {
            "workspace_id": 2,
            "concept_id": 4,
            "concept_name": "Linear Map",
            "flashcards": [{"front": "f", "back": "b", "hint": "h"}],
        },
    )
    _patch(monkeypatch, "apps.api.routes.practice.create_practice_quiz", _quiz_create())
    payload = _submit(with_mastery=False)
    payload["items"][0]["item_type"] = "short_answer"
    payload["items"][0]["result"] = "partial"
    payload["items"][0]["is_correct"] = False
    payload["items"][0]["score"] = 0.5
    _patch(monkeypatch, "apps.api.routes.practice.submit_practice_quiz", payload)
    cards = client.post("/practice/flashcards", json={"workspace_id": 2, "concept_id": 4})
    created = client.post(
        "/practice/quizzes",
        json={"workspace_id": 2, "user_id": 3, "concept_id": 4, "question_count": 4},
    )
    submitted = client.post(
        "/practice/quizzes/1/submit",
        json={"workspace_id": 2, "user_id": 3, "answers": [{"item_id": 11, "answer": "x"}]},
    )
    assert (cards.status_code, created.status_code, submitted.status_code) == (200, 201, 200)
    assert REQUIRED_FIELDS["PracticeFlashcardsResponse"] <= set(cards.json())
    assert REQUIRED_FIELDS["QuizCreateResponse"] <= set(created.json()) and {
        "mastery_status",
        "mastery_score",
    }.isdisjoint(set(submitted.json()))
    assert set(created.json()["items"][0]) == {
        "item_id",
        "position",
        "item_type",
        "prompt",
        "choices",
    }
