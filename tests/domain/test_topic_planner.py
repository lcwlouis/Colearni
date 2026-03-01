"""Tests for topic/subtopic planner (AR5.2)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from domain.research.planner import TopicProposal
from domain.research.topic_planner import (
    _fallback_proposal,
    _parse_proposals,
    plan_topics,
)


class TestFallbackProposal:
    """Test the no-LLM fallback path."""

    def test_basic(self):
        p = _fallback_proposal("Learn quantum computing")
        assert p.topic == "Learn quantum computing"
        assert p.priority == "medium"
        assert p.source_classes == ["article", "docs"]

    def test_truncates_long_goal(self):
        long_goal = "x" * 300
        p = _fallback_proposal(long_goal)
        assert len(p.topic) == 200


class TestParseProposals:
    """Test JSON parsing of LLM output."""

    def test_valid_array(self):
        data = json.dumps([
            {
                "topic": "Quantum Gates",
                "subtopics": ["Hadamard", "CNOT"],
                "source_classes": ["paper", "tutorial"],
                "rationale": "Core building blocks",
                "priority": "high",
            },
            {
                "topic": "Quantum Algorithms",
                "subtopics": ["Shor's", "Grover's"],
                "source_classes": ["paper"],
                "rationale": "Key applications",
                "priority": "medium",
            },
        ])
        proposals = _parse_proposals(data, max_proposals=5)
        assert len(proposals) == 2
        assert proposals[0].topic == "Quantum Gates"
        assert proposals[0].priority == "high"
        assert "Hadamard" in proposals[0].subtopics

    def test_strips_code_fence(self):
        data = "```json\n" + json.dumps([
            {"topic": "ML", "subtopics": [], "source_classes": [], "rationale": "", "priority": "medium"},
        ]) + "\n```"
        proposals = _parse_proposals(data, max_proposals=5)
        assert len(proposals) == 1
        assert proposals[0].topic == "ML"

    def test_caps_at_max_proposals(self):
        items = [{"topic": f"Topic {i}"} for i in range(10)]
        proposals = _parse_proposals(json.dumps(items), max_proposals=3)
        assert len(proposals) == 3

    def test_caps_subtopics(self):
        data = json.dumps([{
            "topic": "ML",
            "subtopics": [f"sub{i}" for i in range(20)],
        }])
        proposals = _parse_proposals(data, max_proposals=5)
        assert len(proposals[0].subtopics) == 5

    def test_invalid_priority_defaults(self):
        data = json.dumps([{"topic": "ML", "priority": "critical"}])
        proposals = _parse_proposals(data, max_proposals=5)
        assert proposals[0].priority == "medium"

    def test_invalid_source_class_filtered(self):
        data = json.dumps([{"topic": "ML", "source_classes": ["paper", "invalid", "docs"]}])
        proposals = _parse_proposals(data, max_proposals=5)
        assert proposals[0].source_classes == ["paper", "docs"]

    def test_empty_array_raises(self):
        try:
            _parse_proposals("[]", max_proposals=5)
            assert False, "Should raise ValueError"
        except ValueError:
            pass

    def test_not_array_raises(self):
        try:
            _parse_proposals('{"topic": "ML"}', max_proposals=5)
            assert False, "Should raise ValueError"
        except ValueError:
            pass


class TestPlanTopics:
    """Test the main plan_topics entry point."""

    def test_empty_goal(self):
        assert plan_topics(goal="") == []
        assert plan_topics(goal="   ") == []

    def test_no_llm_fallback(self):
        proposals = plan_topics(goal="Learn about transformers")
        assert len(proposals) == 1
        assert proposals[0].topic == "Learn about transformers"

    def test_with_llm(self):
        client = MagicMock()
        client.generate_tutor_text.return_value = json.dumps([
            {"topic": "Attention Mechanisms", "subtopics": ["Self-attention"], "source_classes": ["paper"], "rationale": "Core concept", "priority": "high"},
            {"topic": "Transformer Architecture", "subtopics": ["Encoder", "Decoder"], "source_classes": ["tutorial"], "rationale": "Full model", "priority": "medium"},
        ])
        proposals = plan_topics(goal="Learn about transformers", llm_client=client)
        assert len(proposals) == 2
        assert proposals[0].topic == "Attention Mechanisms"
        client.generate_tutor_text.assert_called_once()

    def test_llm_failure_fallback(self):
        client = MagicMock()
        client.generate_tutor_text.side_effect = RuntimeError("LLM down")
        proposals = plan_topics(goal="Learn about transformers", llm_client=client)
        assert len(proposals) == 1
        assert proposals[0].topic == "Learn about transformers"

    def test_llm_bad_json_fallback(self):
        client = MagicMock()
        client.generate_tutor_text.return_value = "not valid json"
        proposals = plan_topics(goal="Learn about transformers", llm_client=client)
        assert len(proposals) == 1  # fallback

    def test_all_proposals_are_frozen(self):
        proposals = plan_topics(goal="ML")
        for p in proposals:
            assert isinstance(p, TopicProposal)
            try:
                p.topic = "changed"  # type: ignore[misc]
                assert False
            except AttributeError:
                pass
