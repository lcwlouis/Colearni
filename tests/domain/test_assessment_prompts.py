"""Tests for P5: Assessment prompt asset migration."""

from __future__ import annotations

import pytest

from core.prompting import PromptRegistry
from domain.learning.quiz_grading import grading_prompt


@pytest.fixture()
def registry() -> PromptRegistry:
    return PromptRegistry()


class TestLevelupGenerateAsset:
    """Tests for assessment/levelup_generate_v1 prompt asset."""

    def test_asset_loads(self, registry: PromptRegistry) -> None:
        asset = registry.get("assessment_levelup_generate_v1")
        assert asset is not None
        assert asset.meta.task_type == "assessment"
        assert asset.meta.version == 1

    def test_asset_renders_with_all_placeholders(self, registry: PromptRegistry) -> None:
        rendered = registry.render("assessment_levelup_generate_v1", {
            "target_count": "7",
            "concept_name": "Photosynthesis",
            "concept_description": "The process by which plants convert light.",
            "adjacent_concepts": "Cellular Respiration, Chloroplast",
            "chunk_excerpts": "Light reactions occur in thylakoids.",
            "chat_history": "Student asked about Calvin cycle.",
        })
        assert "Photosynthesis" in rendered
        assert "7" in rendered
        assert "Cellular Respiration" in rendered
        assert "Light reactions" in rendered
        assert "Calvin cycle" in rendered

    def test_asset_contains_json_output_contract(self, registry: PromptRegistry) -> None:
        rendered = registry.render("assessment_levelup_generate_v1", {
            "target_count": "5",
            "concept_name": "X",
            "concept_description": "Y",
            "adjacent_concepts": "Z",
            "chunk_excerpts": "none",
            "chat_history": "none",
        })
        assert "item_type" in rendered
        assert "short_answer" in rendered
        assert "mcq" in rendered
        assert "rubric_keywords" in rendered
        assert "critical_misconception_keywords" in rendered

    def test_asset_enforces_mastery_gating_language(self, registry: PromptRegistry) -> None:
        rendered = registry.render("assessment_levelup_generate_v1", {
            "target_count": "5",
            "concept_name": "X",
            "concept_description": "Y",
            "adjacent_concepts": "Z",
            "chunk_excerpts": "none",
            "chat_history": "none",
        })
        assert "mastery" in rendered.lower()


class TestLevelupGradeAsset:
    """Tests for assessment/levelup_grade_v1 prompt asset."""

    def test_asset_loads(self, registry: PromptRegistry) -> None:
        asset = registry.get("assessment_levelup_grade_v1")
        assert asset is not None
        assert asset.meta.task_type == "assessment"
        assert asset.meta.version == 1

    def test_asset_renders_with_all_placeholders(self, registry: PromptRegistry) -> None:
        rendered = registry.render("assessment_levelup_grade_v1", {
            "item_ids_json": "[1, 2]",
            "quiz_submission_json": '[{"item_id": 1, "answer": "test"}]',
        })
        assert "[1, 2]" in rendered
        assert "item_id" in rendered

    def test_asset_references_generation_context(self, registry: PromptRegistry) -> None:
        rendered = registry.render("assessment_levelup_grade_v1", {
            "item_ids_json": "[]",
            "quiz_submission_json": "[]",
        })
        assert "_generation_context" in rendered

    def test_asset_contains_json_output_contract(self, registry: PromptRegistry) -> None:
        rendered = registry.render("assessment_levelup_grade_v1", {
            "item_ids_json": "[]",
            "quiz_submission_json": "[]",
        })
        assert "score" in rendered
        assert "critical_misconception" in rendered
        assert "feedback" in rendered
        assert "overall_feedback" in rendered


class TestGradingPromptFunction:
    """Tests that grading_prompt() uses the asset path."""

    def test_grading_prompt_uses_asset(self) -> None:
        items = [
            {"item_id": 1, "item_type": "short_answer", "prompt": "What is X?", "payload": {}},
        ]
        answer_map = {1: "It is Y"}
        result = grading_prompt(items, answer_map)
        # Should contain asset-specific language
        assert "_generation_context" in result
        assert "ITEM_IDS_JSON" in result or "item_ids_json" in result or "[1]" in result

    def test_grading_prompt_includes_submission(self) -> None:
        items = [
            {"item_id": 42, "item_type": "mcq", "prompt": "Pick one", "payload": {}},
        ]
        answer_map = {42: "a"}
        result = grading_prompt(items, answer_map)
        assert "42" in result
