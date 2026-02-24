from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from tests.db.test_level_up_quiz_flow_integration import _client, _seed, _session_or_skip


class PracticeLLM:
    def _count(self, prompt: str, marker: str) -> int:
        return int(
            next(
                line.split(":", 1)[1].strip()
                for line in prompt.splitlines()
                if line.startswith(marker)
            )
        )

    def generate_tutor_text(self, *, prompt: str) -> str:
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
        {"item_id": item["item_id"], "answer": "a" if item["item_type"] == "mcq" else "explain"}
        for item in items
    ]


def test_practice_flashcards_generation_success() -> None:
    session = _session_or_skip()
    workspace_id, _, concept_id = _seed(session)
    app, client = _client(session, PracticeLLM())
    try:
        response = client.post(
            "/practice/flashcards",
            json={"workspace_id": workspace_id, "concept_id": concept_id, "card_count": 4},
        )
        assert response.status_code == 200
        assert len(response.json()["flashcards"]) == 4
    finally:
        _close(session, app, client)


def test_practice_quiz_feedback_mastery_unchanged_and_workspace_scoping() -> None:
    session = _session_or_skip()
    workspace_id, user_id, concept_id = _seed(session)
    wrong_workspace_id, _, _ = _seed(session)
    session.execute(
        text(
            "INSERT INTO mastery (workspace_id, user_id, concept_id, score, status) "
            "VALUES (:w,:u,:c,0.4,'learning')"
        ),
        {"w": workspace_id, "u": user_id, "c": concept_id},
    )
    session.commit()

    app, client = _client(session, PracticeLLM())
    try:
        wrong = client.post(
            "/practice/quizzes",
            json={"workspace_id": wrong_workspace_id, "user_id": user_id, "concept_id": concept_id},
        )
        assert wrong.status_code == 404

        created = client.post(
            "/practice/quizzes",
            json={
                "workspace_id": workspace_id,
                "user_id": user_id,
                "concept_id": concept_id,
                "question_count": 4,
            },
        )
        quiz = created.json()

        wrong_submit = client.post(
            f"/practice/quizzes/{quiz['quiz_id']}/submit",
            json={
                "workspace_id": wrong_workspace_id,
                "user_id": user_id,
                "answers": _answers(quiz["items"]),
            },
        )
        assert wrong_submit.status_code == 404

        submitted = client.post(
            f"/practice/quizzes/{quiz['quiz_id']}/submit",
            json={
                "workspace_id": workspace_id,
                "user_id": user_id,
                "answers": _answers(quiz["items"]),
            },
        )
        payload = submitted.json()
        assert submitted.status_code == 200
        assert isinstance(payload["score"], float)
        assert payload["overall_feedback"]

        mastery = session.execute(
            text("SELECT status, score FROM mastery WHERE user_id=:u AND concept_id=:c"),
            {"u": user_id, "c": concept_id},
        ).mappings().one()
        assert str(mastery["status"]) == "learning"
        assert float(mastery["score"]) == 0.4
    finally:
        _close(session, app, client)
