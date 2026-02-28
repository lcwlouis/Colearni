from __future__ import annotations

import json
from typing import Any

from core.observability import configure_observability, set_event_sink
from core.settings import get_settings
from sqlalchemy import text
from tests.db.test_level_up_quiz_flow_integration import (
    _client,
    _client_without_llm,
    _make_user_row,
    _seed,
    _session_or_skip,
)


class PracticeLLM:
    def _count(self, prompt: str, marker: str) -> int:
        return int(
            next(
                line.split(":", 1)[1].strip()
                for line in prompt.splitlines()
                if line.startswith(marker)
            )
        )

    def generate_tutor_text(self, *, prompt: str, prompt_meta=None) -> str:
        if "CARD_COUNT:" in prompt:
            count = self._count(prompt, "CARD_COUNT:")
            cards = [{"front": "f", "back": "b", "hint": str(i)} for i in range(count)]
            return json.dumps({"flashcards": cards})
        if "QUESTION_COUNT:" in prompt:
            count = self._count(prompt, "QUESTION_COUNT:")
            items = [_short_item(), *[_mcq_item(i) for i in range(2, count + 1)]]
            return json.dumps({"items": items})
        ids = next(
            json.loads(line.split("ITEM_IDS_JSON:", 1)[1].strip())
            for line in prompt.splitlines()
            if line.startswith("ITEM_IDS_JSON:")
        )
        return json.dumps(
            {
                "items": [_graded_item(item_id) for item_id in ids],
                "overall_feedback": "ok",
            }
        )


class FlakyPracticeLLM(PracticeLLM):
    def __init__(self) -> None:
        self.quiz_calls = 0

    def generate_tutor_text(self, *, prompt: str, prompt_meta=None) -> str:
        if "QUESTION_COUNT:" in prompt:
            self.quiz_calls += 1
            if self.quiz_calls == 1:
                return json.dumps(
                    {
                        "items": [
                            _mcq_item(1),
                            _mcq_item(2),
                            _mcq_item(3),
                            _mcq_item(4),
                        ]
                    }
                )
        return super().generate_tutor_text(prompt=prompt, prompt_meta=prompt_meta)


def _short_item() -> dict[str, Any]:
    return {
        "item_type": "short_answer",
        "prompt": "Explain concept.",
        "payload": {
            "rubric_keywords": ["linear", "map"],
            "critical_misconception_keywords": ["contradiction"],
        },
    }


def _mcq_item(index: int) -> dict[str, Any]:
    return {
        "item_type": "mcq",
        "prompt": f"mcq {index}",
        "payload": {
            "choices": [{"id": "a", "text": "Correct"}, {"id": "b", "text": "Wrong"}],
            "correct_choice_id": "a",
            "critical_choice_ids": ["b"],
            "choice_explanations": {"a": "Correct", "b": "Critical wrong"},
        },
    }


def _graded_item(item_id: int) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "score": 1.0,
        "critical_misconception": False,
        "feedback": "ok",
    }


def _close(session: Any, app: Any, client: Any) -> None:
    app.dependency_overrides.clear()
    client.close()
    bind = session.get_bind()
    session.close()
    if bind is not None:
        bind.dispose()


def _answers(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "item_id": item["item_id"],
            "answer": item["choices"][0]["id"]
            if item["item_type"] == "mcq" and item.get("choices")
            else ("a" if item["item_type"] == "mcq" else "explain"),
        }
        for item in items
    ]


def test_practice_flashcards_generation_success() -> None:
    session = _session_or_skip()
    workspace_id, ws_pid, user_id, concept_id = _seed(session)
    mock_user = _make_user_row(session, user_id)
    app, client = _client(session, PracticeLLM(), user=mock_user)
    try:
        response = client.post(
            f"/workspaces/{ws_pid}/practice/flashcards",
            json={"concept_id": concept_id, "card_count": 4},
        )
        assert response.status_code == 200
        assert len(response.json()["flashcards"]) == 4
    finally:
        _close(session, app, client)


def test_practice_quiz_feedback_mastery_unchanged_and_workspace_scoping() -> None:
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
    workspace_id, ws_pid, user_id, concept_id = _seed(session)
    _wrong_workspace_id, wrong_ws_pid, _wrong_user_id, _ = _seed(session)
    session.execute(
        text(
            "INSERT INTO mastery (workspace_id, user_id, concept_id, score, status) "
            "VALUES (:w,:u,:c,0.4,'learning')"
        ),
        {"w": workspace_id, "u": user_id, "c": concept_id},
    )
    session.commit()

    mock_user = _make_user_row(session, user_id)
    app, client = _client(session, PracticeLLM(), user=mock_user)
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
        # User is not a member of wrong workspace → 403
        wrong = client.post(
            f"/workspaces/{wrong_ws_pid}/practice/quizzes",
            json={"concept_id": concept_id, "question_count": 4},
        )
        assert wrong.status_code == 403

        created = client.post(
            f"/workspaces/{ws_pid}/practice/quizzes",
            json={
                "concept_id": concept_id,
                "question_count": 4,
            },
        )
        quiz = created.json()

        # Submit to wrong workspace → 403
        wrong_submit = client.post(
            f"/workspaces/{wrong_ws_pid}/practice/quizzes/{quiz['quiz_id']}/submit",
            json={
                "answers": _answers(quiz["items"]),
            },
        )
        assert wrong_submit.status_code == 403

        submitted = client.post(
            f"/workspaces/{ws_pid}/practice/quizzes/{quiz['quiz_id']}/submit",
            json={
                "answers": _answers(quiz["items"]),
            },
        )
        payload = submitted.json()
        assert submitted.status_code == 200
        assert isinstance(payload["score"], float)
        assert payload["overall_feedback"]
        assert isinstance(payload["items"], list)
        assert "mastery_status" not in payload
        assert "mastery_score" not in payload
        assert len(payload["items"]) == len(quiz["items"])
        for item in payload["items"]:
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

        mastery = session.execute(
            text("SELECT status, score FROM mastery WHERE user_id=:u AND concept_id=:c"),
            {"u": user_id, "c": concept_id},
        ).mappings().one()
        assert str(mastery["status"]) == "learning"
        assert float(mastery["score"]) == 0.4
        assert any(event["event_name"] == "grading.practice.start" for event in events)
        assert any(event["event_name"] == "grading.practice.result" for event in events)
    finally:
        _close(session, app, client)
        set_event_sink(None)


def test_practice_quiz_generation_retries_when_first_payload_is_invalid() -> None:
    session = _session_or_skip()
    workspace_id, ws_pid, user_id, concept_id = _seed(session)
    mock_user = _make_user_row(session, user_id)
    llm = FlakyPracticeLLM()
    app, client = _client(session, llm, user=mock_user)
    try:
        created = client.post(
            f"/workspaces/{ws_pid}/practice/quizzes",
            json={
                "concept_id": concept_id,
                "question_count": 4,
            },
        )
        assert created.status_code == 201
        assert llm.quiz_calls == 2
    finally:
        _close(session, app, client)


def test_practice_quiz_create_and_submit_without_llm_uses_fallback() -> None:
    session = _session_or_skip()
    workspace_id, ws_pid, user_id, concept_id = _seed(session)
    mock_user = _make_user_row(session, user_id)
    app, client = _client_without_llm(session, user=mock_user)
    try:
        created = client.post(
            f"/workspaces/{ws_pid}/practice/quizzes",
            json={
                "concept_id": concept_id,
                "question_count": 4,
            },
        )
        assert created.status_code == 201
        quiz = created.json()
        assert len(quiz["items"]) == 4
        assert {item["item_type"] for item in quiz["items"]} == {"short_answer", "mcq"}

        submitted = client.post(
            f"/workspaces/{ws_pid}/practice/quizzes/{quiz['quiz_id']}/submit",
            json={
                "answers": _answers(quiz["items"]),
            },
        )
        assert submitted.status_code == 200
        payload = submitted.json()
        assert payload["overall_feedback"]
        assert len(payload["items"]) == len(quiz["items"])
    finally:
        _close(session, app, client)


def test_practice_quiz_submit_failure_emits_observability_event() -> None:
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
    workspace_id, ws_pid, user_id, concept_id = _seed(session)
    mock_user = _make_user_row(session, user_id)
    app, client = _client(session, PracticeLLM(), user=mock_user)
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
            f"/workspaces/{ws_pid}/practice/quizzes",
            json={
                "concept_id": concept_id,
                "question_count": 4,
            },
        )
        assert created.status_code == 201
        quiz = created.json()

        submitted = client.post(
            f"/workspaces/{ws_pid}/practice/quizzes/{quiz['quiz_id']}/submit",
            json={
                "answers": _answers(quiz["items"])[:1],
            },
        )
        assert submitted.status_code == 422
        assert any(event["event_name"] == "grading.practice.start" for event in events)
        assert any(event["event_name"] == "grading.practice.failure" for event in events)
    finally:
        _close(session, app, client)
        set_event_sink(None)
