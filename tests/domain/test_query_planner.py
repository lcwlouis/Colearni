"""Tests for query planning and candidate queue integration (AR5.3)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from domain.research.planner import TopicProposal
from domain.research.query_planner import (
    _fallback_query_plan,
    _parse_queries,
    build_query_plan,
    enqueue_query_results,
)


class TestParseQueries:
    """Test JSON parsing of LLM query output."""

    def test_valid_array(self):
        data = json.dumps([
            {"query_text": "attention mechanism tutorial", "source_class": "tutorial", "max_results": 5},
            {"query_text": "transformer architecture paper", "source_class": "paper", "max_results": 3},
        ])
        queries = _parse_queries(data, max_queries=8)
        assert len(queries) == 2
        assert queries[0].query_text == "attention mechanism tutorial"
        assert queries[0].source_class == "tutorial"
        assert queries[1].max_results == 3

    def test_caps_at_max_queries(self):
        items = [{"query_text": f"q{i}"} for i in range(15)]
        queries = _parse_queries(json.dumps(items), max_queries=3)
        assert len(queries) == 3

    def test_invalid_source_class_defaults(self):
        data = json.dumps([{"query_text": "test", "source_class": "invalid"}])
        queries = _parse_queries(data, max_queries=8)
        assert queries[0].source_class == "other"

    def test_max_results_capped(self):
        data = json.dumps([{"query_text": "test", "max_results": 100}])
        queries = _parse_queries(data, max_queries=8)
        assert queries[0].max_results == 10

    def test_strips_code_fence(self):
        data = "```json\n" + json.dumps([{"query_text": "test"}]) + "\n```"
        queries = _parse_queries(data, max_queries=8)
        assert len(queries) == 1

    def test_not_array_raises(self):
        try:
            _parse_queries('{"query_text": "test"}', max_queries=8)
            assert False, "Should raise ValueError"
        except ValueError:
            pass


class TestFallbackQueryPlan:
    """Test the no-LLM fallback query plan."""

    def test_basic(self):
        proposal = TopicProposal(topic="Quantum Computing")
        plan = _fallback_query_plan(proposal, max_queries=5)
        assert plan.topic == "Quantum Computing"
        assert len(plan.queries) == 1
        assert plan.queries[0].query_text == "Quantum Computing"

    def test_with_subtopics(self):
        proposal = TopicProposal(
            topic="ML",
            subtopics=["Supervised Learning", "Neural Networks", "CNNs"],
            source_classes=["paper"],
        )
        plan = _fallback_query_plan(proposal, max_queries=5)
        assert len(plan.queries) == 4  # 1 main + 3 subtopics
        assert plan.queries[1].query_text == "ML Supervised Learning"
        assert plan.queries[1].source_class == "paper"

    def test_caps_queries(self):
        proposal = TopicProposal(
            topic="ML",
            subtopics=[f"sub{i}" for i in range(20)],
        )
        plan = _fallback_query_plan(proposal, max_queries=3)
        assert len(plan.queries) == 3


class TestBuildQueryPlan:
    """Test the main build_query_plan entry point."""

    def test_no_llm_fallback(self):
        proposal = TopicProposal(topic="ML")
        plan = build_query_plan(proposal=proposal)
        assert plan.topic == "ML"
        assert plan.is_bounded

    def test_with_llm(self):
        client = MagicMock()
        client.generate_tutor_text.return_value = json.dumps([
            {"query_text": "attention mechanism", "source_class": "paper", "max_results": 5},
        ])
        proposal = TopicProposal(topic="Transformers")
        plan = build_query_plan(proposal=proposal, llm_client=client)
        assert len(plan.queries) == 1
        assert plan.queries[0].query_text == "attention mechanism"

    def test_llm_failure_fallback(self):
        client = MagicMock()
        client.generate_tutor_text.side_effect = RuntimeError("LLM down")
        proposal = TopicProposal(topic="Transformers")
        plan = build_query_plan(proposal=proposal, llm_client=client)
        assert plan.topic == "Transformers"
        assert plan.is_bounded


class TestEnqueueQueryResults:
    """Test candidate queue insertion."""

    def test_inserts_candidates(self):
        session = MagicMock()
        results = [
            {"source_url": "https://example.com/1", "title": "Article 1", "snippet": "Content 1"},
            {"source_url": "https://example.com/2", "title": "Article 2"},
        ]
        count = enqueue_query_results(session, workspace_id=1, run_id=10, results=results)
        assert count == 2
        assert session.execute.call_count == 2
        session.commit.assert_called_once()

    def test_skips_empty_urls(self):
        session = MagicMock()
        results = [
            {"source_url": "", "title": "No URL"},
            {"source_url": "https://example.com", "title": "Valid"},
        ]
        count = enqueue_query_results(session, workspace_id=1, run_id=10, results=results)
        assert count == 1

    def test_empty_results(self):
        session = MagicMock()
        count = enqueue_query_results(session, workspace_id=1, run_id=10, results=[])
        assert count == 0
        session.commit.assert_not_called()

    def test_caps_at_max(self):
        session = MagicMock()
        results = [{"source_url": f"https://example.com/{i}"} for i in range(50)]
        count = enqueue_query_results(session, workspace_id=1, run_id=10, results=results)
        assert count == 25  # _MAX_CANDIDATES_PER_PLAN

    def test_insert_failure_continues(self):
        session = MagicMock()
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("DB error")
        session.execute.side_effect = side_effect
        results = [
            {"source_url": "https://fail.com"},
            {"source_url": "https://ok.com"},
        ]
        count = enqueue_query_results(session, workspace_id=1, run_id=10, results=results)
        assert count == 1
