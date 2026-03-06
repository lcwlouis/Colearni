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

    def generate_tutor_text(self, *, prompt: str, prompt_meta=None, system_prompt=None) -> str:
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

    def generate_tutor_text(self, *, prompt: str, prompt_meta=None, system_prompt=None) -> str:
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
        return super().generate_tutor_text(prompt=prompt, prompt_meta=prompt_meta, system_prompt=system_prompt)


class ExplodingPracticeLLM:
    def generate_tutor_text(self, *, prompt: str, prompt_meta=None, system_prompt=None) -> str:
        raise RuntimeError("synthetic llm failure")


class UniqueFlashcardLLM(PracticeLLM):
    def generate_tutor_text(self, *, prompt: str, prompt_meta=None, system_prompt=None) -> str:
        if "CARD_COUNT:" in prompt:
            count = self._count(prompt, "CARD_COUNT:")
            cards = [
                {"front": f"f{idx}", "back": f"b{idx}", "hint": f"h{idx}"}
                for idx in range(count)
            ]
            return json.dumps({"flashcards": cards})
        return super().generate_tutor_text(prompt=prompt, prompt_meta=prompt_meta, system_prompt=system_prompt)


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


def test_practice_quiz_fallback_clamps_overfetch_with_seen_history() -> None:
    session = _session_or_skip()
    workspace_id, ws_pid, user_id, concept_id = _seed(session)
    for idx in range(6):
        session.execute(
            text(
                """
                INSERT INTO practice_item_history
                    (workspace_id, user_id, concept_id, item_type, fingerprint)
                VALUES (:workspace_id, :user_id, :concept_id, 'quiz', :fingerprint)
                """
            ),
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "concept_id": concept_id,
                "fingerprint": f"fp-{idx}",
            },
        )
    session.commit()

    mock_user = _make_user_row(session, user_id)
    app, client = _client(session, ExplodingPracticeLLM(), user=mock_user)
    try:
        created = client.post(
            f"/workspaces/{ws_pid}/practice/quizzes",
            json={
                "concept_id": concept_id,
                "question_count": 6,
            },
        )
        assert created.status_code == 201
        quiz = created.json()
        assert len(quiz["items"]) == 6
        assert {item["item_type"] for item in quiz["items"]} == {"short_answer", "mcq"}
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


def test_practice_quiz_history_list_and_detail_with_latest_attempt() -> None:
    session = _session_or_skip()
    workspace_id, ws_pid, user_id, concept_id = _seed(session)
    _wrong_workspace_id, wrong_ws_pid, _wrong_user_id, _ = _seed(session)
    mock_user = _make_user_row(session, user_id)
    app, client = _client(session, PracticeLLM(), user=mock_user)
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

        listed_before = client.get(
            f"/workspaces/{ws_pid}/practice/quizzes",
            params={"concept_id": concept_id},
        )
        assert listed_before.status_code == 200
        before_payload = listed_before.json()
        assert before_payload["workspace_id"] == workspace_id
        assert before_payload["user_id"] == user_id
        assert before_payload["concept_id"] == concept_id
        assert len(before_payload["quizzes"]) >= 1
        first_before = before_payload["quizzes"][0]
        assert first_before["quiz_id"] == quiz["quiz_id"]
        assert first_before["latest_attempt"] is None

        submitted = client.post(
            f"/workspaces/{ws_pid}/practice/quizzes/{quiz['quiz_id']}/submit",
            json={
                "answers": _answers(quiz["items"]),
            },
        )
        assert submitted.status_code == 200

        listed_after = client.get(
            f"/workspaces/{ws_pid}/practice/quizzes",
            params={"concept_id": concept_id},
        )
        assert listed_after.status_code == 200
        after_payload = listed_after.json()
        first_after = after_payload["quizzes"][0]
        assert first_after["quiz_id"] == quiz["quiz_id"]
        assert first_after["item_count"] == len(quiz["items"])
        assert first_after["latest_attempt"] is not None
        assert set(first_after["latest_attempt"].keys()) == {
            "attempt_id",
            "score",
            "passed",
            "critical_misconception",
            "overall_feedback",
            "graded_at",
            "grading_items",
        }

        detail = client.get(
            f"/workspaces/{ws_pid}/practice/quizzes/{quiz['quiz_id']}",
        )
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["quiz_id"] == quiz["quiz_id"]
        assert len(detail_payload["items"]) == len(quiz["items"])
        assert detail_payload["latest_attempt"] is not None

        wrong_workspace_detail = client.get(
            f"/workspaces/{wrong_ws_pid}/practice/quizzes/{quiz['quiz_id']}",
        )
        assert wrong_workspace_detail.status_code == 403
    finally:
        _close(session, app, client)


def test_stateful_flashcard_runs_list_and_detail_with_progress() -> None:
    session = _session_or_skip()
    workspace_id, ws_pid, user_id, concept_id = _seed(session)
    _wrong_workspace_id, wrong_ws_pid, _wrong_user_id, _ = _seed(session)
    mock_user = _make_user_row(session, user_id)
    app, client = _client(session, UniqueFlashcardLLM(), user=mock_user)
    try:
        generated = client.post(
            f"/workspaces/{ws_pid}/practice/flashcards/stateful",
            json={"concept_id": concept_id, "card_count": 3},
        )
        assert generated.status_code == 200
        gen_payload = generated.json()
        run_id = gen_payload["run_id"]
        assert len(gen_payload["flashcards"]) == 3

        runs = client.get(
            f"/workspaces/{ws_pid}/practice/flashcards/runs",
            params={"concept_id": concept_id},
        )
        assert runs.status_code == 200
        runs_payload = runs.json()
        assert runs_payload["workspace_id"] == workspace_id
        assert runs_payload["user_id"] == user_id
        assert runs_payload["concept_id"] == concept_id
        assert any(run["run_id"] == run_id for run in runs_payload["runs"])

        first_card_id = gen_payload["flashcards"][0]["flashcard_id"]
        rated = client.post(
            f"/workspaces/{ws_pid}/practice/flashcards/rate",
            json={"flashcard_id": first_card_id, "self_rating": "good"},
        )
        assert rated.status_code == 200

        detail = client.get(
            f"/workspaces/{ws_pid}/practice/flashcards/runs/{run_id}",
        )
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["run_id"] == run_id
        assert len(detail_payload["flashcards"]) == 3
        updated_card = next(card for card in detail_payload["flashcards"] if card["flashcard_id"] == first_card_id)
        assert updated_card["self_rating"] == "good"
        assert updated_card["passed"] is True
        assert "due_at" in updated_card
        assert "interval_days" in updated_card

        wrong_workspace_detail = client.get(
            f"/workspaces/{wrong_ws_pid}/practice/flashcards/runs/{run_id}",
        )
        assert wrong_workspace_detail.status_code == 403
    finally:
        _close(session, app, client)
