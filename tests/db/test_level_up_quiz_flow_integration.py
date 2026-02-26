from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from adapters.db.dependencies import get_db_session
from apps.api.main import create_app
from core.observability import configure_observability, set_event_sink
from core.settings import get_settings
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class DeterministicQuizGrader:
    def __init__(self, *, score: float, critical: bool) -> None:
        self.score = score
        self.critical = critical
        self.calls = 0
        self.last_prompt: str | None = None

    def generate_tutor_text(self, *, prompt: str) -> str:
        self.calls += 1
        self.last_prompt = prompt
        marker = "ITEM_IDS_JSON:"
        ids = next(
            json.loads(line.split(marker, maxsplit=1)[1].strip())
            for line in prompt.splitlines()
            if line.startswith(marker)
        )
        return json.dumps(
            {
                "items": [
                    {
                        "item_id": item_id,
                        "score": self.score,
                        "critical_misconception": self.critical and index == 0,
                        "feedback": "ok",
                    }
                    for index, item_id in enumerate(ids)
                ],
                "overall_feedback": "ok",
            }
        )


def _session_or_skip() -> Session:
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        session = Session(bind=engine)
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        engine.dispose()
        pytest.skip(f"Postgres unavailable: {exc}")
    return session


def _seed(session: Session) -> tuple[int, int, int]:
    suffix = uuid.uuid4().hex
    user_id = int(
        session.execute(
            text("INSERT INTO users (email) VALUES (:email) RETURNING id"),
            {"email": f"quiz-{suffix}@example.com"},
        ).scalar_one()
    )
    workspace_id = int(
        session.execute(
            text(
                "INSERT INTO workspaces (name, owner_user_id) "
                "VALUES (:name, :owner_user_id) RETURNING id"
            ),
            {"name": f"ws-{suffix}", "owner_user_id": user_id},
        ).scalar_one()
    )
    concept_id = int(
        session.execute(
            text(
                """
                INSERT INTO concepts_canon (workspace_id, canonical_name, description, aliases)
                VALUES (:workspace_id, 'Linear Map', 'Preserves vector operations.', :aliases)
                RETURNING id
                """
            ),
            {"workspace_id": workspace_id, "aliases": ["Linear Transformation"]},
        ).scalar_one()
    )
    session.commit()
    return workspace_id, user_id, concept_id


def _client(session: Session, grader: DeterministicQuizGrader) -> tuple[Any, TestClient]:
    app = create_app(settings=get_settings().model_copy(update={"ingest_build_graph": False}))
    app.state.graph_llm_client = grader

    def override_db() -> Any:
        yield session

    app.dependency_overrides[get_db_session] = override_db
    return app, TestClient(app)


def _client_without_llm(session: Session) -> tuple[Any, TestClient]:
    app = create_app(settings=get_settings().model_copy(update={"ingest_build_graph": False}))

    def override_db() -> Any:
        yield session

    app.dependency_overrides[get_db_session] = override_db
    return app, TestClient(app)


def _answers(items: list[dict[str, Any]], *, mcq: str) -> list[dict[str, Any]]:
    return [
        {
            "item_id": item["item_id"],
            "answer": mcq if item["item_type"] == "mcq" else "explain",
        }
        for item in items
    ]


@pytest.mark.parametrize(
    ("score", "critical", "seed_mastery", "expected_pass", "expected_status", "mcq"),
    [
        (1.0, False, False, True, "learned", "a"),
        (0.3, True, True, False, "learning", "d"),
    ],
)
def test_level_up_pass_fail_transitions(
    score: float,
    critical: bool,
    seed_mastery: bool,
    expected_pass: bool,
    expected_status: str,
    mcq: str,
) -> None:
    events: list[dict[str, Any]] = []
    set_event_sink(events)
    configure_observability(
        get_settings().model_copy(
            update={
                "observability_enabled": True,
                "observability_otlp_endpoint": None,
                "observability_service_name": "colearni-test",
            }
        )
    )
    session = _session_or_skip()
    grader = DeterministicQuizGrader(score=score, critical=critical)
    workspace_id, user_id, concept_id = _seed(session)
    if seed_mastery:
        session.execute(
            text(
                """
                INSERT INTO mastery (workspace_id, user_id, concept_id, score, status)
                VALUES (:workspace_id, :user_id, :concept_id, 1.0, 'learned')
                """
            ),
            {"workspace_id": workspace_id, "user_id": user_id, "concept_id": concept_id},
        )
        session.commit()
    app, client = _client(session, grader)
    configure_observability(
        get_settings().model_copy(
            update={
                "observability_enabled": True,
                "observability_otlp_endpoint": None,
                "observability_service_name": "colearni-test",
            }
        )
    )

    try:
        created = client.post(
            "/quizzes/level-up",
            json={
                "workspace_id": workspace_id,
                "user_id": user_id,
                "concept_id": concept_id,
                "question_count": 5,
            },
        )
        assert created.status_code == 201
        create_payload = created.json()
        item_types = {item["item_type"] for item in create_payload["items"]}
        assert item_types == {"short_answer", "mcq"}
        create_items_by_type = {item["item_type"]: item for item in create_payload["items"]}
        assert create_items_by_type["short_answer"]["choices"] is None
        assert create_items_by_type["mcq"]["choices"] == [
            {"id": choice["id"], "text": choice["text"]}
            for choice in create_items_by_type["mcq"]["choices"]
        ]
        assert "correct_choice_id" not in create_items_by_type["mcq"]
        assert "critical_choice_ids" not in create_items_by_type["mcq"]
        assert "choice_explanations" not in create_items_by_type["mcq"]
        assert "_generation_context" not in create_items_by_type["mcq"]
        mcq_payload = session.execute(
            text(
                """
                SELECT payload
                FROM quiz_items
                WHERE quiz_id = :quiz_id AND item_type = 'mcq'
                ORDER BY position
                LIMIT 1
                """
            ),
            {"quiz_id": create_payload["quiz_id"]},
        ).scalar_one()
        assert isinstance(mcq_payload.get("choice_explanations"), dict)
        assert set(mcq_payload["choice_explanations"].keys()) == {
            choice["id"] for choice in mcq_payload["choices"]
        }
        short_payload = session.execute(
            text(
                """
                SELECT payload
                FROM quiz_items
                WHERE quiz_id = :quiz_id AND item_type = 'short_answer'
                ORDER BY position
                LIMIT 1
                """
            ),
            {"quiz_id": create_payload["quiz_id"]},
        ).scalar_one()
        generation_context = short_payload.get("_generation_context")
        assert isinstance(generation_context, dict)
        assert generation_context.get("concept_name") == "Linear Map"
        assert generation_context.get("context_source") == "generated"
        assert isinstance(generation_context.get("context_keywords"), list)
        assert generation_context["context_keywords"]

        submitted = client.post(
            f"/quizzes/{create_payload['quiz_id']}/submit",
            json={
                "workspace_id": workspace_id,
                "user_id": user_id,
                "answers": _answers(create_payload["items"], mcq=mcq),
            },
        )
        assert submitted.status_code == 200
        submit_payload = submitted.json()
        assert submit_payload["passed"] is expected_pass
        assert submit_payload["mastery_status"] == expected_status
        assert isinstance(submit_payload["mastery_score"], float)
        assert 0.0 <= submit_payload["mastery_score"] <= 1.0
        assert isinstance(submit_payload["overall_feedback"], str)
        assert submit_payload["overall_feedback"]
        assert isinstance(submit_payload["items"], list)
        assert len(submit_payload["items"]) == len(create_payload["items"])
        for item in submit_payload["items"]:
            assert set(item.keys()) == {
                "item_id",
                "item_type",
                "result",
                "is_correct",
                "critical_misconception",
                "feedback",
                "score",
            }
            assert item["item_type"] in {"short_answer", "mcq"}
            assert item["result"] in {"correct", "partial", "incorrect"}
            assert isinstance(item["is_correct"], bool)
            assert isinstance(item["critical_misconception"], bool)
            assert isinstance(item["feedback"], str)
            assert item["feedback"]
            assert isinstance(item["score"], float)
            assert 0.0 <= item["score"] <= 1.0

        mcq_items = [item for item in submit_payload["items"] if item["item_type"] == "mcq"]
        assert mcq_items
        if mcq == "a":
            assert all(item["result"] == "correct" for item in mcq_items)
            assert all(item["is_correct"] is True for item in mcq_items)
            assert all(item["score"] == 1.0 for item in mcq_items)
        else:
            assert all(item["result"] == "incorrect" for item in mcq_items)
            assert all(item["is_correct"] is False for item in mcq_items)
            assert all(item["score"] == 0.0 for item in mcq_items)

        grading = session.execute(
            text(
                """
                SELECT grading
                FROM quiz_attempts
                WHERE quiz_id = :quiz_id
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"quiz_id": create_payload["quiz_id"]},
        ).scalar_one()
        assert isinstance(grading, dict)
        assert isinstance(grading.get("overall_feedback"), str)
        assert isinstance(grading.get("items"), list)
        assert grading["items"]
        grading_item = grading["items"][0]
        assert set(grading_item.keys()) == {
            "item_id",
            "item_type",
            "result",
            "is_correct",
            "critical_misconception",
            "feedback",
            "score",
        }
        assert grader.last_prompt is not None
        assert "_generation_context" in grader.last_prompt
        assert any(event["event_name"] == "grading.level_up.start" for event in events)
        assert any(event["event_name"] == "grading.level_up.result" for event in events)

        mastery_status = session.execute(
            text(
                """
                SELECT status
                FROM mastery
                WHERE workspace_id = :workspace_id
                  AND user_id = :user_id
                  AND concept_id = :concept_id
                """
            ),
            {"workspace_id": workspace_id, "user_id": user_id, "concept_id": concept_id},
        ).scalar_one()
        assert mastery_status == expected_status
    finally:
        app.dependency_overrides.clear()
        client.close()
        bind = session.get_bind()
        session.close()
        if bind is not None:
            bind.dispose()
        set_event_sink(None)


def test_level_up_submit_replay_is_idempotent() -> None:
    session = _session_or_skip()
    grader = DeterministicQuizGrader(score=0.9, critical=False)
    workspace_id, user_id, concept_id = _seed(session)
    app, client = _client(session, grader)

    try:
        created = client.post(
            "/quizzes/level-up",
            json={"workspace_id": workspace_id, "user_id": user_id, "concept_id": concept_id},
        )
        quiz = created.json()
        first = client.post(
            f"/quizzes/{quiz['quiz_id']}/submit",
            json={
                "workspace_id": workspace_id,
                "user_id": user_id,
                "answers": _answers(quiz["items"], mcq="a"),
            },
        )
        second = client.post(
            f"/quizzes/{quiz['quiz_id']}/submit",
            json={
                "workspace_id": workspace_id,
                "user_id": user_id,
                "answers": _answers(quiz["items"], mcq="d"),
            },
        )
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["replayed"] is True
        assert second.json()["attempt_id"] == first.json()["attempt_id"]
        assert second.json()["retry_hint"] == "create a new level-up quiz to retry"
        assert second.json()["overall_feedback"] == first.json()["overall_feedback"]
        assert second.json()["items"] == first.json()["items"]
        assert second.json()["items"]
        assert grader.calls == 1

        attempts = int(
            session.execute(
                text(
                    "SELECT count(*) FROM quiz_attempts "
                    "WHERE quiz_id = :quiz_id AND user_id = :user_id"
                ),
                {"quiz_id": quiz["quiz_id"], "user_id": user_id},
            ).scalar_one()
        )
        assert attempts == 1
    finally:
        app.dependency_overrides.clear()
        client.close()
        bind = session.get_bind()
        session.close()
        if bind is not None:
            bind.dispose()


def test_level_up_submit_failure_emits_observability_event() -> None:
    events: list[dict[str, Any]] = []
    set_event_sink(events)
    configure_observability(
        get_settings().model_copy(
            update={
                "observability_enabled": True,
                "observability_otlp_endpoint": None,
                "observability_service_name": "colearni-test",
            }
        )
    )
    session = _session_or_skip()
    grader = DeterministicQuizGrader(score=0.8, critical=False)
    workspace_id, user_id, concept_id = _seed(session)
    app, client = _client(session, grader)
    configure_observability(
        get_settings().model_copy(
            update={
                "observability_enabled": True,
                "observability_otlp_endpoint": None,
                "observability_service_name": "colearni-test",
            }
        )
    )

    try:
        created = client.post(
            "/quizzes/level-up",
            json={
                "workspace_id": workspace_id,
                "user_id": user_id,
                "concept_id": concept_id,
                "question_count": 5,
            },
        )
        assert created.status_code == 201
        quiz = created.json()

        submitted = client.post(
            f"/quizzes/{quiz['quiz_id']}/submit",
            json={
                "workspace_id": workspace_id,
                "user_id": user_id,
                "answers": _answers(quiz["items"], mcq="a")[:1],
            },
        )
        assert submitted.status_code == 422
        assert any(event["event_name"] == "grading.level_up.start" for event in events)
        assert any(event["event_name"] == "grading.level_up.failure" for event in events)
    finally:
        app.dependency_overrides.clear()
        client.close()
        bind = session.get_bind()
        session.close()
        if bind is not None:
            bind.dispose()
        set_event_sink(None)


def test_level_up_mcq_only_submission_works_without_llm() -> None:
    session = _session_or_skip()
    workspace_id, user_id, concept_id = _seed(session)
    app, client = _client_without_llm(session)
    items = [
        {
            "item_type": "mcq",
            "prompt": f"MCQ question {index}",
            "payload": {
                "choices": [
                    {"id": "a", "text": "Correct"},
                    {"id": "b", "text": "Wrong"},
                ],
                "correct_choice_id": "a",
                "critical_choice_ids": ["b"],
                "choice_explanations": {
                    "a": "Correct because it matches the concept.",
                    "b": "Incorrect and critical because it contradicts the concept.",
                },
            },
        }
        for index in range(1, 6)
    ]
    try:
        created = client.post(
            "/quizzes/level-up",
            json={
                "workspace_id": workspace_id,
                "user_id": user_id,
                "concept_id": concept_id,
                "items": items,
            },
        )
        assert created.status_code == 201
        quiz = created.json()
        assert all(item["choices"] for item in quiz["items"])
        assert all("correct_choice_id" not in item for item in quiz["items"])
        assert all("critical_choice_ids" not in item for item in quiz["items"])
        mcq_payload = session.execute(
            text(
                """
                SELECT payload
                FROM quiz_items
                WHERE quiz_id = :quiz_id
                ORDER BY position
                LIMIT 1
                """
            ),
            {"quiz_id": quiz["quiz_id"]},
        ).scalar_one()
        generation_context = mcq_payload.get("_generation_context")
        assert isinstance(generation_context, dict)
        assert generation_context.get("context_source") == "provided"

        submitted = client.post(
            f"/quizzes/{quiz['quiz_id']}/submit",
            json={
                "workspace_id": workspace_id,
                "user_id": user_id,
                "answers": _answers(quiz["items"], mcq="a"),
            },
        )
        assert submitted.status_code == 200
        payload = submitted.json()
        assert payload["passed"] is True
        assert "MCQ correctness" in payload["overall_feedback"]
        assert payload["overall_feedback"]
        assert payload["items"]
        assert all(item["item_type"] == "mcq" for item in payload["items"])
        assert all(item["result"] == "correct" for item in payload["items"])
        assert all(item["is_correct"] is True for item in payload["items"])
        assert all(item["score"] == 1.0 for item in payload["items"])
    finally:
        app.dependency_overrides.clear()
        client.close()
        bind = session.get_bind()
        session.close()
        if bind is not None:
            bind.dispose()
