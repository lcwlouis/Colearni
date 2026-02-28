"""Unit tests for quiz_gardener background job logic."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from apps.jobs.quiz_gardener import MAX_CONCEPTS_PER_RUN, run_quiz_gardener


class _FakeMappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> "_FakeMappings":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class _FakeSession:
    def __init__(self, candidates: list[dict[str, Any]]) -> None:
        self.candidates = candidates
        self.quiz_created: list[dict[str, Any]] = []

    def execute(self, *args: Any, **kwargs: Any) -> _FakeMappings:  # noqa: ARG002
        return _FakeMappings(self.candidates)

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


def test_quiz_gardener_no_llm_skips(caplog: Any) -> None:
    """When no LLM client is available, the gardener should skip gracefully."""
    with (
        patch("apps.jobs.quiz_gardener.build_graph_llm_client", side_effect=ValueError("no key")),
        patch("apps.jobs.quiz_gardener.create_db_engine"),
    ):
        run_quiz_gardener()
    assert "no LLM client available" in caplog.text


def test_quiz_gardener_no_candidates_logs_info(caplog: Any) -> None:
    """When no concepts need quizzes, the gardener should log and exit."""
    mock_session = _FakeSession(candidates=[])
    with (
        patch("apps.jobs.quiz_gardener.build_graph_llm_client", return_value=MagicMock()),
        patch("apps.jobs.quiz_gardener.create_db_engine"),
        patch("apps.jobs.quiz_gardener.Session", return_value=mock_session),
    ):
        import logging

        with caplog.at_level(logging.INFO):
            run_quiz_gardener()
    assert "no concepts need auto-quiz generation" in caplog.text


def test_quiz_gardener_creates_quizzes_for_candidates() -> None:
    """The gardener should call create_level_up_quiz for each candidate."""
    candidates = [
        {"workspace_id": 1, "user_id": 10, "concept_id": 100, "canonical_name": "Vector Space"},
        {"workspace_id": 1, "user_id": 10, "concept_id": 101, "canonical_name": "Eigenvalue"},
    ]
    mock_session = _FakeSession(candidates=candidates)
    mock_llm = MagicMock()
    mock_create = MagicMock(return_value={"quiz_id": 1})

    with (
        patch("apps.jobs.quiz_gardener.build_graph_llm_client", return_value=mock_llm),
        patch("apps.jobs.quiz_gardener.create_db_engine"),
        patch("apps.jobs.quiz_gardener.Session", return_value=mock_session),
        patch("apps.jobs.quiz_gardener.create_level_up_quiz", mock_create),
    ):
        run_quiz_gardener()

    assert mock_create.call_count == 2
    # Verify correct args passed
    first_call = mock_create.call_args_list[0]
    assert first_call.kwargs["concept_id"] == 100
    assert first_call.kwargs["context_source"] == "auto_gardener"


def test_quiz_gardener_continues_after_single_failure(caplog: Any) -> None:
    """If one quiz creation fails, the gardener should continue to the next."""
    candidates = [
        {"workspace_id": 1, "user_id": 10, "concept_id": 100, "canonical_name": "Fails"},
        {"workspace_id": 1, "user_id": 10, "concept_id": 101, "canonical_name": "Succeeds"},
    ]
    mock_session = _FakeSession(candidates=candidates)
    mock_llm = MagicMock()
    call_count = 0

    def _create_side_effect(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("LLM timeout")
        return {"quiz_id": 2}

    with (
        patch("apps.jobs.quiz_gardener.build_graph_llm_client", return_value=mock_llm),
        patch("apps.jobs.quiz_gardener.create_db_engine"),
        patch("apps.jobs.quiz_gardener.Session", return_value=mock_session),
        patch("apps.jobs.quiz_gardener.create_level_up_quiz", side_effect=_create_side_effect),
    ):
        import logging

        with caplog.at_level(logging.INFO):
            run_quiz_gardener()

    assert "Created 1 quizzes" in caplog.text
    assert "failed" in caplog.text.lower()


def test_max_concepts_per_run_is_bounded() -> None:
    """Verify the per-run cap is set to a reasonable value."""
    assert MAX_CONCEPTS_PER_RUN == 20
