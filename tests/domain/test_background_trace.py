"""Tests for background trace state helper (AR6.5)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from domain.chat.background_trace import (
    BackgroundTraceState,
    fetch_background_trace_state,
)


class TestBackgroundTraceState:
    """Unit tests for BackgroundTraceState dataclass."""

    def test_defaults(self) -> None:
        state = BackgroundTraceState()
        assert state.digest_available is False
        assert state.frontier_suggestion_count == 0
        assert state.research_candidate_pending == 0
        assert state.research_candidate_approved == 0

    def test_custom_values(self) -> None:
        state = BackgroundTraceState(
            digest_available=True,
            frontier_suggestion_count=5,
            research_candidate_pending=3,
            research_candidate_approved=2,
        )
        assert state.digest_available is True
        assert state.frontier_suggestion_count == 5
        assert state.research_candidate_pending == 3
        assert state.research_candidate_approved == 2


class TestFetchBackgroundTraceState:
    """Tests for fetch_background_trace_state()."""

    def test_returns_defaults_on_exception(self) -> None:
        """Should return safe defaults if DB query fails."""
        session = MagicMock()
        session.execute.side_effect = Exception("db gone")
        state = fetch_background_trace_state(session, workspace_id=1, user_id=1)
        assert state == BackgroundTraceState()

    def test_no_digests_no_candidates(self) -> None:
        """No digest rows and no candidates → all defaults except digest_available."""
        session = MagicMock()
        # First call: learner_digests query → no rows
        first_exec = MagicMock()
        first_exec.mappings.return_value.first.return_value = None

        # Third call: candidate status counts → no rows
        third_exec = MagicMock()
        third_exec.mappings.return_value.all.return_value = []

        session.execute.side_effect = [first_exec, third_exec]

        state = fetch_background_trace_state(session, workspace_id=1, user_id=1)
        assert state.digest_available is False
        assert state.frontier_suggestion_count == 0
        assert state.research_candidate_pending == 0
        assert state.research_candidate_approved == 0

    def test_digest_exists_no_frontier(self) -> None:
        """Has a digest but no frontier_suggestions type."""
        session = MagicMock()

        # First call: learner_digests exists
        first_exec = MagicMock()
        first_exec.mappings.return_value.first.return_value = {
            "digest_type": "learner_summary",
            "payload": {"summary": "test"},
        }

        # Second call: frontier_suggestions query → no row
        second_exec = MagicMock()
        second_exec.mappings.return_value.first.return_value = None

        # Third call: candidate counts
        third_exec = MagicMock()
        third_exec.mappings.return_value.all.return_value = [
            {"status": "pending", "cnt": 7},
            {"status": "approved", "cnt": 3},
        ]

        session.execute.side_effect = [first_exec, second_exec, third_exec]

        state = fetch_background_trace_state(session, workspace_id=1, user_id=1)
        assert state.digest_available is True
        assert state.frontier_suggestion_count == 0
        assert state.research_candidate_pending == 7
        assert state.research_candidate_approved == 3

    def test_digest_with_frontier_suggestions(self) -> None:
        """Has frontier_suggestions digest with items."""
        session = MagicMock()

        first_exec = MagicMock()
        first_exec.mappings.return_value.first.return_value = {
            "digest_type": "frontier_suggestions",
            "payload": {"suggestions": ["a", "b", "c"]},
        }

        second_exec = MagicMock()
        second_exec.mappings.return_value.first.return_value = {
            "payload": {"suggestions": ["a", "b", "c"]},
        }

        third_exec = MagicMock()
        third_exec.mappings.return_value.all.return_value = []

        session.execute.side_effect = [first_exec, second_exec, third_exec]

        state = fetch_background_trace_state(session, workspace_id=1, user_id=1)
        assert state.digest_available is True
        assert state.frontier_suggestion_count == 3

    def test_candidate_counts_parsed(self) -> None:
        """Candidate status counts are correctly mapped."""
        session = MagicMock()

        first_exec = MagicMock()
        first_exec.mappings.return_value.first.return_value = None

        third_exec = MagicMock()
        third_exec.mappings.return_value.all.return_value = [
            {"status": "pending", "cnt": 10},
            {"status": "approved", "cnt": 4},
            {"status": "rejected", "cnt": 2},
            {"status": "ingested", "cnt": 1},
        ]

        session.execute.side_effect = [first_exec, third_exec]

        state = fetch_background_trace_state(session, workspace_id=1, user_id=1)
        assert state.research_candidate_pending == 10
        assert state.research_candidate_approved == 4


class TestTracePopulationCallsite:
    """Prove that respond.py and stream.py call fetch_background_trace_state."""

    def test_respond_imports_background_trace(self) -> None:
        """respond.py imports fetch_background_trace_state."""
        import importlib
        import inspect

        mod = importlib.import_module("domain.chat.respond")
        source = inspect.getsource(mod)
        assert "fetch_background_trace_state" in source
        assert "bg_state.digest_available" in source

    def test_stream_imports_background_trace(self) -> None:
        """stream.py imports fetch_background_trace_state."""
        import importlib
        import inspect

        mod = importlib.import_module("domain.chat.stream")
        source = inspect.getsource(mod)
        assert "fetch_background_trace_state" in source
        assert "bg_state.digest_available" in source

    def test_respond_sets_all_four_bg_fields(self) -> None:
        """respond.py trace enrichment includes all 4 bg_ fields."""
        import importlib
        import inspect

        source = inspect.getsource(
            importlib.import_module("domain.chat.respond")
        )
        for field in [
            "bg_digest_available",
            "bg_frontier_suggestion_count",
            "bg_research_candidate_pending",
            "bg_research_candidate_approved",
        ]:
            assert field in source, f"{field} not found in respond.py"

    def test_stream_sets_all_four_bg_fields(self) -> None:
        """stream.py trace enrichment includes all 4 bg_ fields."""
        import importlib
        import inspect

        source = inspect.getsource(
            importlib.import_module("domain.chat.stream")
        )
        for field in [
            "bg_digest_available",
            "bg_frontier_suggestion_count",
            "bg_research_candidate_pending",
            "bg_research_candidate_approved",
        ]:
            assert field in source, f"{field} not found in stream.py"
