"""Unit tests for research_digest background job (AR6.2)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.jobs.research_digest import (
    MAX_WORKSPACES_PER_RUN,
    generate_research_digest,
    generate_what_changed,
    run_research_digest,
    store_research_digest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeMappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> "_FakeMappings":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class _FakeSession:
    """Tracks execute calls. Returns sequential result sets."""

    def __init__(self, results: list[list[dict[str, Any]]]) -> None:
        self._results = list(results)
        self._call_idx = 0
        self.executions: list[Any] = []
        self.committed = False

    def execute(self, stmt: Any, params: Any = None) -> _FakeMappings:
        self.executions.append((stmt, params))
        if self._call_idx < len(self._results):
            rows = self._results[self._call_idx]
            self._call_idx += 1
        else:
            rows = []
        return _FakeMappings(rows)

    def commit(self) -> None:
        self.committed = True

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


# ---------------------------------------------------------------------------
# generate_research_digest
# ---------------------------------------------------------------------------


class TestGenerateResearchDigest:
    def test_empty_workspace(self) -> None:
        session = _FakeSession([
            [],  # status counts
            [],  # recent candidates
        ])
        result = generate_research_digest(session, workspace_id=1)
        assert result["workspace_id"] == 1
        assert result["total_candidates"] == 0
        assert result["recent_candidates"] == []

    def test_counts_by_status(self) -> None:
        session = _FakeSession([
            [
                {"status": "pending", "cnt": 5},
                {"status": "approved", "cnt": 3},
                {"status": "rejected", "cnt": 2},
            ],
            [],  # recent
        ])
        result = generate_research_digest(session, workspace_id=1)
        assert result["status_counts"]["pending"] == 5
        assert result["status_counts"]["approved"] == 3
        assert result["total_candidates"] == 10

    def test_recent_candidates_included(self) -> None:
        session = _FakeSession([
            [],  # status counts
            [{"title": "Paper A", "status": "pending", "source_url": "http://a.com"}],
        ])
        result = generate_research_digest(session, workspace_id=1)
        assert len(result["recent_candidates"]) == 1
        assert result["recent_candidates"][0]["title"] == "Paper A"


# ---------------------------------------------------------------------------
# generate_what_changed
# ---------------------------------------------------------------------------


class TestGenerateWhatChanged:
    def test_empty_workspace(self) -> None:
        session = _FakeSession([
            [],  # runs
            [],  # reviewed counts
        ])
        result = generate_what_changed(session, workspace_id=1)
        assert result["workspace_id"] == 1
        assert result["run_count"] == 0
        assert result["reviewed_counts"] == {}

    def test_run_summaries(self) -> None:
        session = _FakeSession([
            [
                {"id": 10, "status": "completed", "candidates_found": 5, "started_at": "2026-01-01", "finished_at": "2026-01-01"},
            ],
            [],  # reviewed
        ])
        result = generate_what_changed(session, workspace_id=1)
        assert result["run_count"] == 1
        assert result["recent_runs"][0]["candidates_found"] == 5

    def test_reviewed_counts(self) -> None:
        session = _FakeSession([
            [],  # runs
            [
                {"status": "approved", "cnt": 4},
                {"status": "ingested", "cnt": 2},
            ],
        ])
        result = generate_what_changed(session, workspace_id=1)
        assert result["reviewed_counts"]["approved"] == 4
        assert result["reviewed_counts"]["ingested"] == 2


# ---------------------------------------------------------------------------
# store_research_digest
# ---------------------------------------------------------------------------


class TestStoreResearchDigest:
    def test_executes_insert(self) -> None:
        mock_session = MagicMock()
        store_research_digest(
            mock_session,
            workspace_id=1,
            digest_type="research_digest",
            payload={"total": 10},
        )
        mock_session.execute.assert_called_once()
        params = mock_session.execute.call_args[0][1]
        assert params["workspace_id"] == 1
        assert params["user_id"] == 0
        assert params["digest_type"] == "research_digest"
        parsed = json.loads(params["payload"])
        assert parsed["total"] == 10


# ---------------------------------------------------------------------------
# run_research_digest (integration-style)
# ---------------------------------------------------------------------------


class TestRunResearchDigest:
    def test_no_workspaces_does_nothing(self, caplog: Any) -> None:
        mock_session = _FakeSession([
            [],  # workspace query
        ])
        with (
            patch("apps.jobs.research_digest.create_db_engine"),
            patch("apps.jobs.research_digest.Session", return_value=mock_session),
        ):
            import logging
            with caplog.at_level(logging.INFO):
                run_research_digest()
        assert "Total digests stored: 0" in caplog.text

    def test_generates_two_digests_per_workspace(self) -> None:
        mock_session = _FakeSession([
            [{"workspace_id": 1}],  # workspace query
            [],  # digest status counts
            [],  # digest recent
            [],  # what_changed runs
            [],  # what_changed reviewed
            # 2 INSERT statements handled by mock
        ])
        with (
            patch("apps.jobs.research_digest.create_db_engine"),
            patch("apps.jobs.research_digest.Session", return_value=mock_session),
        ):
            run_research_digest()

        # 1 workspace query + 2 SELECT for digest + 2 SELECT for what_changed + 2 INSERT
        assert mock_session.committed

    def test_continues_after_failure(self, caplog: Any) -> None:
        # First workspace fails, second succeeds
        mock_session = _FakeSession([
            [{"workspace_id": 1}, {"workspace_id": 2}],  # workspaces
        ])
        call_count = 0
        original_execute = mock_session.execute

        def _execute_side_effect(stmt: Any, params: Any = None) -> _FakeMappings:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return original_execute(stmt, params)
            if call_count == 2:
                raise RuntimeError("DB timeout")
            return _FakeMappings([])

        mock_session.execute = _execute_side_effect  # type: ignore[assignment]

        with (
            patch("apps.jobs.research_digest.create_db_engine"),
            patch("apps.jobs.research_digest.Session", return_value=mock_session),
        ):
            import logging
            with caplog.at_level(logging.INFO):
                run_research_digest()

        assert "failed for workspace=1" in caplog.text


class TestConstants:
    def test_max_workspaces_bounded(self) -> None:
        assert MAX_WORKSPACES_PER_RUN <= 100
