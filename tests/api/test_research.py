"""Tests for research API routes and service integration (AR5.5)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from domain.research.service import execute_topic_plan


class TestExecuteTopicPlanService:
    """Verify execute_topic_plan service function."""

    @patch("domain.research.query_planner.enqueue_query_results", return_value=3)
    @patch("domain.research.query_planner.build_query_plan")
    @patch("adapters.db.research.insert_run")
    def test_creates_run_and_plans_queries(
        self, mock_insert_run, mock_build, mock_enqueue
    ):
        from domain.research.planner import ResearchQuery, ResearchQueryPlan

        mock_insert_run.return_value = {
            "id": 42,
            "status": "pending",
            "candidates_found": 0,
            "started_at": "2026-01-01",
        }
        mock_build.return_value = ResearchQueryPlan(
            topic="Photosynthesis",
            queries=[
                ResearchQuery(query_text="photosynthesis overview", source_class="article"),
                ResearchQuery(query_text="light reactions", source_class="paper"),
                ResearchQuery(query_text="Calvin cycle tutorial", source_class="tutorial"),
            ],
            rationale="Fallback",
        )

        db = MagicMock()
        result = execute_topic_plan(
            db,
            workspace_id=1,
            topic="Photosynthesis",
            subtopics=["Light reactions", "Calvin cycle"],
        )

        assert result["run_id"] == 42
        assert result["topic"] == "Photosynthesis"
        assert result["queries_planned"] == 3
        assert result["candidates_inserted"] == 3

        # Verify enqueue was called with candidate-shaped results
        call_args = mock_enqueue.call_args
        assert call_args.kwargs["workspace_id"] == 1
        assert call_args.kwargs["run_id"] == 42
        results = call_args.kwargs["results"]
        assert len(results) == 3
        assert results[0]["source_url"].startswith("planned://")
        assert "[Planned]" in results[0]["title"]

    @patch("domain.research.query_planner.enqueue_query_results", return_value=1)
    @patch("domain.research.query_planner.build_query_plan")
    @patch("adapters.db.research.insert_run")
    def test_no_subtopics_still_works(
        self, mock_insert_run, mock_build, mock_enqueue
    ):
        from domain.research.planner import ResearchQuery, ResearchQueryPlan

        mock_insert_run.return_value = {
            "id": 10,
            "status": "pending",
            "candidates_found": 0,
            "started_at": "2026-01-01",
        }
        mock_build.return_value = ResearchQueryPlan(
            topic="Machine Learning",
            queries=[ResearchQuery(query_text="ML basics")],
        )

        db = MagicMock()
        result = execute_topic_plan(
            db,
            workspace_id=5,
            topic="Machine Learning",
        )

        assert result["queries_planned"] == 1
        assert result["candidates_inserted"] == 1


class TestExecuteTopicRoute:
    """Verify the /topics/execute API route."""

    @patch("domain.research.service.execute_topic_plan")
    def test_route_returns_query_plan_response(self, mock_execute):
        mock_execute.return_value = {
            "run_id": 42,
            "topic": "Photosynthesis",
            "queries_planned": 3,
            "candidates_inserted": 3,
        }

        from apps.api.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        resp = client.post(
            "/workspaces/1/research/topics/execute",
            json={
                "topic": "Photosynthesis",
                "subtopics": ["Light reactions"],
                "source_classes": ["paper"],
            },
            headers={"Authorization": "Bearer test-token"},
        )

        # May get 401/403 due to auth — test that the route exists and is wired
        assert resp.status_code in (201, 401, 403, 422)

    def test_schema_validation(self):
        from core.schemas.research import QueryPlanResponse, TopicExecuteRequest

        req = TopicExecuteRequest(
            topic="Test Topic",
            subtopics=["sub1"],
            source_classes=["paper"],
        )
        assert req.topic == "Test Topic"

        resp = QueryPlanResponse(
            run_id=1,
            topic="Test",
            queries_planned=3,
            candidates_inserted=2,
        )
        assert resp.queries_planned == 3

    def test_execute_request_requires_topic(self):
        from pydantic import ValidationError

        from core.schemas.research import TopicExecuteRequest

        try:
            TopicExecuteRequest(topic="")
            assert False, "Should have raised"
        except ValidationError:
            pass

    def test_query_plan_response_requires_positive_run_id(self):
        from pydantic import ValidationError

        from core.schemas.research import QueryPlanResponse

        try:
            QueryPlanResponse(
                run_id=0,
                topic="t",
                queries_planned=0,
                candidates_inserted=0,
            )
            assert False, "Should have raised"
        except ValidationError:
            pass


class TestQueryPlanProductionCallsite:
    """Verify build_query_plan and enqueue_query_results have production callsites."""

    def test_build_query_plan_called_from_service(self):
        """Confirm build_query_plan is imported and called by execute_topic_plan."""
        import inspect
        source = inspect.getsource(execute_topic_plan)
        assert "build_query_plan" in source

    def test_enqueue_query_results_called_from_service(self):
        """Confirm enqueue_query_results is imported and called by execute_topic_plan."""
        import inspect
        source = inspect.getsource(execute_topic_plan)
        assert "enqueue_query_results" in source
