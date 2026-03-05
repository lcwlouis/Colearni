"""Tests for format_hierarchy_prompt_context."""

from domain.chat.retrieval_context import format_hierarchy_prompt_context


def test_all_fields_populated():
    result = format_hierarchy_prompt_context(
        session_topic_name="Machine Learning",
        active_concept_name="Backpropagation",
        active_concept_tier="subtopic",
        ancestor_context="Concept hierarchy (from parent to root): Neural Networks → Machine Learning → AI",
    )
    assert "TOPIC HIERARCHY CONTEXT:" in result
    assert "Current session topic: Machine Learning" in result
    assert "Active concept: Backpropagation (subtopic)" in result
    assert "Hierarchy: AI → Machine Learning → Neural Networks → Backpropagation" in result
    assert "Stay aware of the broader context." in result


def test_session_topic_name_none():
    result = format_hierarchy_prompt_context(
        session_topic_name=None,
        active_concept_name="Backpropagation",
        active_concept_tier="subtopic",
        ancestor_context="Concept hierarchy (from parent to root): Neural Networks → Machine Learning",
    )
    assert "TOPIC HIERARCHY CONTEXT:" in result
    assert "Current session topic" not in result
    assert "Active concept: Backpropagation (subtopic)" in result
    assert "Hierarchy: Machine Learning → Neural Networks → Backpropagation" in result


def test_active_concept_name_none_returns_empty():
    result = format_hierarchy_prompt_context(
        session_topic_name="Machine Learning",
        active_concept_name=None,
        active_concept_tier="subtopic",
        ancestor_context="Concept hierarchy (from parent to root): Neural Networks → ML",
    )
    assert result == ""


def test_empty_ancestor_context():
    result = format_hierarchy_prompt_context(
        session_topic_name="Machine Learning",
        active_concept_name="Backpropagation",
        active_concept_tier="granular",
        ancestor_context="",
    )
    assert "TOPIC HIERARCHY CONTEXT:" in result
    assert "Current session topic: Machine Learning" in result
    assert "Active concept: Backpropagation (granular)" in result
    assert "Hierarchy: Backpropagation" in result
    assert "Stay aware of the broader context." in result


def test_no_tier_label_when_tier_is_none():
    result = format_hierarchy_prompt_context(
        session_topic_name="AI",
        active_concept_name="Neural Networks",
        active_concept_tier=None,
        ancestor_context="",
    )
    assert "Active concept: Neural Networks\n" in result
    assert "(None)" not in result
