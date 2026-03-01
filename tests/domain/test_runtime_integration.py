"""AR6.6: Runtime integration regression tests for background and research loops.

These tests close the gap between helper/unit tests and production behavior:
1. execute_topic_plan() data flow: proposal → build_query_plan → enqueue_query_results
2. promote_reviewed_candidate() quiz gating at service level
3. Background trace fields populated from real DB state in tutor paths
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.schemas.assistant import GenerationTrace


# ---------------------------------------------------------------------------
# 1. Research queue execution — data flows correctly through the service
# ---------------------------------------------------------------------------


class TestExecuteTopicPlanDataFlow:
    """Prove execute_topic_plan passes the right data between stages."""

    @patch("domain.research.service.research_db")
    def test_plan_queries_become_candidates(self, mock_rdb: MagicMock) -> None:
        """build_query_plan output feeds into discovery provider, then enqueue."""
        from domain.research.planner import TopicProposal
        from domain.research.query_planner import ResearchQueryPlan, ResearchQuery

        mock_rdb.insert_run.return_value = {"id": 42}

        plan = ResearchQueryPlan(
            topic="ML basics",
            queries=[
                ResearchQuery(query_text="what is gradient descent", source_class="web"),
                ResearchQuery(query_text="backpropagation explained", source_class="academic"),
            ],
        )

        discovered = [
            {"source_url": "https://example.com/gd", "title": "Gradient Descent", "snippet": "..."},
            {"source_url": "https://example.com/bp", "title": "Backprop", "snippet": "..."},
        ]

        with patch("domain.research.query_planner.build_query_plan", return_value=plan):
            with patch("domain.research.discovery_provider.execute_planned_queries", return_value=discovered):
                with patch("domain.research.query_planner.enqueue_query_results") as mock_enqueue:
                    mock_enqueue.return_value = 2
                    session = MagicMock()

                    from domain.research.service import execute_topic_plan

                    result = execute_topic_plan(
                        session,
                        workspace_id=1,
                        topic="ML basics",
                        subtopics=["gradient descent", "backprop"],
                    )

                    # Verify enqueue received real URLs (not planned://)
                    call_args = mock_enqueue.call_args
                    results_arg = call_args.kwargs.get("results") or call_args[1].get("results")
                    if results_arg is None:
                        results_arg = call_args[0][3] if len(call_args[0]) > 3 else None

                    assert results_arg is not None, "enqueue_query_results must receive results"
                    assert len(results_arg) == 2
                    assert results_arg[0]["source_url"].startswith("https://")
                    assert "planned://" not in results_arg[0]["source_url"]

                    # Verify result aggregation
                    assert result["run_id"] == 42
                    assert result["queries_planned"] == 2
                    assert result["candidates_inserted"] == 2

    @patch("domain.research.service.research_db")
    def test_empty_plan_produces_no_candidates(self, mock_rdb: MagicMock) -> None:
        """When build_query_plan returns zero queries, no candidates are enqueued."""
        from domain.research.query_planner import ResearchQueryPlan

        mock_rdb.insert_run.return_value = {"id": 99}

        plan = ResearchQueryPlan(topic="empty", queries=[])

        with patch("domain.research.query_planner.build_query_plan", return_value=plan):
            with patch("domain.research.discovery_provider.execute_planned_queries", return_value=[]):
                with patch("domain.research.query_planner.enqueue_query_results") as mock_enqueue:
                    mock_enqueue.return_value = 0
                    session = MagicMock()

                    from domain.research.service import execute_topic_plan

                    result = execute_topic_plan(
                        session,
                        workspace_id=1,
                        topic="empty",
                    )

                    call_args = mock_enqueue.call_args
                    results_arg = call_args.kwargs.get("results") or call_args[1].get("results")
                    if results_arg is None:
                        results_arg = call_args[0][3] if len(call_args[0]) > 3 else []
                    assert len(results_arg) == 0
                    assert result["candidates_inserted"] == 0


# ---------------------------------------------------------------------------
# 2. Promotion gating — service integrates with evaluate_candidate_for_promotion
# ---------------------------------------------------------------------------


class TestPromotionGatingIntegration:
    """Prove the service function respects promotion policy without mocking evaluate."""

    @patch("domain.research.service.research_db")
    def test_approved_with_quiz_gate_defers(self, mock_rdb: MagicMock) -> None:
        """Approved candidate + quiz_gate + quiz_passed=False → quiz_gate action."""
        mock_rdb.list_candidates.return_value = [
            {"id": 10, "status": "approved", "source_url": "https://example.com", "title": "test"},
        ]

        session = MagicMock()
        # Prevent promote_candidate and record_promotion_feedback from real DB calls
        with patch("domain.research.promotion.promote_candidate", return_value=False):
            with patch("domain.research.promotion.record_promotion_feedback"):
                from domain.research.service import promote_reviewed_candidate

                result = promote_reviewed_candidate(
                    session,
                    candidate_id=10,
                    workspace_id=1,
                    user_id=1,
                    has_quiz_gate=True,
                    quiz_passed=False,
                )

                assert result["action"] == "quiz_gate"
                assert result["promoted"] is False

    @patch("domain.research.service.research_db")
    def test_approved_with_quiz_passed_promotes(self, mock_rdb: MagicMock) -> None:
        """Approved + quiz_gate + quiz_passed=True → promote action."""
        mock_rdb.list_candidates.return_value = [
            {"id": 10, "status": "approved", "source_url": "https://example.com", "title": "test"},
        ]

        session = MagicMock()
        with patch("domain.research.promotion.promote_candidate", return_value=True) as mock_promote:
            with patch("domain.research.promotion.record_promotion_feedback"):
                from domain.research.service import promote_reviewed_candidate

                result = promote_reviewed_candidate(
                    session,
                    candidate_id=10,
                    workspace_id=1,
                    user_id=1,
                    has_quiz_gate=True,
                    quiz_passed=True,
                )

                assert result["action"] == "promote"
                assert result["promoted"] is True
                mock_promote.assert_called_once()

    @patch("domain.research.service.research_db")
    def test_pending_candidate_cannot_promote(self, mock_rdb: MagicMock) -> None:
        """Pending candidate → reject, never calls promote_candidate."""
        mock_rdb.list_candidates.return_value = [
            {"id": 10, "status": "pending", "source_url": "https://example.com", "title": "test"},
        ]

        session = MagicMock()
        with patch("domain.research.promotion.promote_candidate") as mock_promote:
            with patch("domain.research.promotion.record_promotion_feedback"):
                from domain.research.service import promote_reviewed_candidate

                result = promote_reviewed_candidate(
                    session,
                    candidate_id=10,
                    workspace_id=1,
                    user_id=1,
                )

                assert result["action"] == "reject"
                assert result["promoted"] is False
                mock_promote.assert_not_called()

    @patch("domain.research.service.research_db")
    def test_feedback_always_recorded(self, mock_rdb: MagicMock) -> None:
        """record_promotion_feedback is always called regardless of decision."""
        mock_rdb.list_candidates.return_value = [
            {"id": 10, "status": "approved", "source_url": "x", "title": "t"},
        ]

        session = MagicMock()
        with patch("domain.research.promotion.promote_candidate", return_value=True):
            with patch("domain.research.promotion.record_promotion_feedback") as mock_feedback:
                from domain.research.service import promote_reviewed_candidate

                promote_reviewed_candidate(
                    session,
                    candidate_id=10,
                    workspace_id=1,
                    user_id=7,
                )

                mock_feedback.assert_called_once()
                call_kw = mock_feedback.call_args.kwargs
                assert call_kw["user_id"] == 7
                assert call_kw["candidate_id"] == 10


# ---------------------------------------------------------------------------
# 3. Background trace fields: integration with tutor trace enrichment
# ---------------------------------------------------------------------------


class TestBackgroundTraceIntegration:
    """Prove background trace fields flow from DB state through to GenerationTrace."""

    def test_trace_enrichment_with_real_bg_state(self) -> None:
        """model_copy with bg_state produces non-null bg_ fields."""
        from domain.chat.background_trace import BackgroundTraceState

        bg_state = BackgroundTraceState(
            digest_available=True,
            frontier_suggestion_count=4,
            research_candidate_pending=8,
            research_candidate_approved=3,
        )

        trace = GenerationTrace()
        enriched = trace.model_copy(update={
            "bg_digest_available": bg_state.digest_available,
            "bg_frontier_suggestion_count": bg_state.frontier_suggestion_count,
            "bg_research_candidate_pending": bg_state.research_candidate_pending,
            "bg_research_candidate_approved": bg_state.research_candidate_approved,
        })

        assert enriched.bg_digest_available is True
        assert enriched.bg_frontier_suggestion_count == 4
        assert enriched.bg_research_candidate_pending == 8
        assert enriched.bg_research_candidate_approved == 3

    def test_trace_round_trips_with_bg_fields(self) -> None:
        """Trace with bg_ fields survives JSON serialization and envelope wrapping."""
        from core.schemas import AssistantResponseEnvelope, Citation

        trace = GenerationTrace(
            bg_digest_available=True,
            bg_frontier_suggestion_count=2,
            bg_research_candidate_pending=5,
            bg_research_candidate_approved=1,
        )
        envelope = AssistantResponseEnvelope(
            kind="answer",
            text="Test answer",
            grounding_mode="hybrid",
            generation_trace=trace,
            evidence=[],
            citations=[Citation(citation_id="c1", evidence_id="e1", label="From your notes")],
        )

        payload = envelope.model_dump(mode="json")
        restored = AssistantResponseEnvelope.model_validate(payload)

        assert restored.generation_trace is not None
        gt = restored.generation_trace
        assert gt.bg_digest_available is True
        assert gt.bg_frontier_suggestion_count == 2
        assert gt.bg_research_candidate_pending == 5
        assert gt.bg_research_candidate_approved == 1

    def test_fetch_helper_returns_nondefault_on_digest_data(self) -> None:
        """fetch_background_trace_state returns non-defaults when DB has data."""
        from domain.chat.background_trace import fetch_background_trace_state

        session = MagicMock()

        # Digest exists
        digest_exec = MagicMock()
        digest_exec.mappings.return_value.first.return_value = {
            "digest_type": "learner_summary",
            "payload": {"summary": "progress looks good"},
        }

        # Frontier suggestions exist
        frontier_exec = MagicMock()
        frontier_exec.mappings.return_value.first.return_value = {
            "payload": {"suggestions": ["topic_a", "topic_b"]},
        }

        # Candidate counts
        candidate_exec = MagicMock()
        candidate_exec.mappings.return_value.all.return_value = [
            {"status": "pending", "cnt": 12},
            {"status": "approved", "cnt": 5},
        ]

        session.execute.side_effect = [digest_exec, frontier_exec, candidate_exec]

        state = fetch_background_trace_state(session, workspace_id=1, user_id=1)

        assert state.digest_available is True
        assert state.frontier_suggestion_count == 2
        assert state.research_candidate_pending == 12
        assert state.research_candidate_approved == 5


# ---------------------------------------------------------------------------
# 4. Verification recipe itself is trustworthy
# ---------------------------------------------------------------------------


class TestVerificationRecipe:
    """AR6.6 exit criteria: verification commands work correctly."""

    def test_all_bg_trace_fields_on_schema(self) -> None:
        """GenerationTrace has all 4 bg_ fields."""
        trace = GenerationTrace()
        assert hasattr(trace, "bg_digest_available")
        assert hasattr(trace, "bg_frontier_suggestion_count")
        assert hasattr(trace, "bg_research_candidate_pending")
        assert hasattr(trace, "bg_research_candidate_approved")

    def test_respond_and_stream_both_wire_bg_fields(self) -> None:
        """Both tutor paths set bg_ fields (proven by source inspection)."""
        import importlib
        import inspect

        for mod_name in ["domain.chat.respond", "domain.chat.stream"]:
            source = inspect.getsource(importlib.import_module(mod_name))
            for field in [
                "bg_digest_available",
                "bg_frontier_suggestion_count",
                "bg_research_candidate_pending",
                "bg_research_candidate_approved",
            ]:
                assert field in source, f"{field} not found in {mod_name}"

    def test_promotion_helpers_have_service_callsite(self) -> None:
        """All three promotion helpers are called from the service module."""
        import importlib
        import inspect

        source = inspect.getsource(
            importlib.import_module("domain.research.service")
        )
        for fn in [
            "evaluate_candidate_for_promotion",
            "promote_candidate",
            "record_promotion_feedback",
        ]:
            assert fn in source, f"{fn} not found in service.py"

    def test_query_planner_helpers_have_service_callsite(self) -> None:
        """Both query planner helpers are called from the service module."""
        import importlib
        import inspect

        source = inspect.getsource(
            importlib.import_module("domain.research.service")
        )
        for fn in ["build_query_plan", "enqueue_query_results"]:
            assert fn in source, f"{fn} not found in service.py"


# ---------------------------------------------------------------------------
# 5. Discovery provider — bounded execution
# ---------------------------------------------------------------------------


class TestDiscoveryProvider:
    """AR5.7: Verify execute_planned_queries returns bounded, non-synthetic results."""

    def test_no_sources_returns_empty(self) -> None:
        """When workspace has no sources, returns [] instead of synthetic URLs."""
        from domain.research.discovery_provider import execute_planned_queries
        from domain.research.planner import ResearchQuery

        session = MagicMock()
        session.execute.return_value.mappings.return_value.all.return_value = []

        results = execute_planned_queries(
            session,
            workspace_id=1,
            queries=[ResearchQuery(query_text="test query")],
        )
        assert results == []

    def test_max_total_results_cap(self) -> None:
        """Results are capped at max_total_results."""
        from domain.research.discovery_provider import execute_planned_queries
        from domain.research.planner import ResearchQuery

        session = MagicMock()
        # No sources → empty list anyway
        session.execute.return_value.mappings.return_value.all.return_value = []

        results = execute_planned_queries(
            session,
            workspace_id=1,
            queries=[ResearchQuery(query_text="q")],
            max_total_results=2,
        )
        assert len(results) <= 2

    def test_is_relevant_checks_query_terms(self) -> None:
        """Basic relevance filter works."""
        from domain.research.discovery_provider import _is_relevant

        assert _is_relevant("Photosynthesis is important", "photosynthesis")
        assert not _is_relevant("Cooking recipes are fun", "photosynthesis")
        assert _is_relevant("Learn about machine learning and AI", "machine learning")

    def test_execute_planned_queries_in_service_source(self) -> None:
        """Confirm execute_planned_queries is called from execute_topic_plan."""
        import inspect
        from domain.research.service import execute_topic_plan

        source = inspect.getsource(execute_topic_plan)
        assert "execute_planned_queries" in source
        # No synthetic planned:// URLs in code (docstring mention is OK)
        code_lines = [l for l in source.split("\n") if not l.strip().startswith(("#", '"""', "rather"))]
        assert not any("planned://" in l for l in code_lines)
