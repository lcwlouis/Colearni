"""Tests for P6: Practice prompt asset migration."""

from __future__ import annotations

import pytest

from core.prompting import PromptRegistry


@pytest.fixture()
def registry() -> PromptRegistry:
    return PromptRegistry()


class TestPracticeQuizGenerateAsset:
    """Tests for practice/practice_quiz_generate_v1 prompt asset."""

    def test_asset_loads(self, registry: PromptRegistry) -> None:
        asset = registry.get("practice_practice_quiz_generate_v1")
        assert asset is not None
        assert asset.meta.task_type == "practice"
        assert asset.meta.version == 1

    def test_asset_renders_with_all_placeholders(self, registry: PromptRegistry) -> None:
        rendered = registry.render("practice_practice_quiz_generate_v1", {
            "question_count": "7",
            "context_json": '{"concept_name": "Photosynthesis"}',
            "novelty_seed": "abc-123",
        })
        assert "QUESTION_COUNT: 7" in rendered
        assert "Photosynthesis" in rendered
        assert "abc-123" in rendered

    def test_asset_contains_json_output_contract(self, registry: PromptRegistry) -> None:
        rendered = registry.render("practice_practice_quiz_generate_v1", {
            "question_count": "5",
            "context_json": "{}",
            "novelty_seed": "x",
        })
        assert "item_type" in rendered
        assert "short_answer" in rendered
        assert "mcq" in rendered
        assert "rubric_keywords" in rendered

    def test_asset_preserves_novelty_behavior(self, registry: PromptRegistry) -> None:
        rendered = registry.render("practice_practice_quiz_generate_v1", {
            "question_count": "5",
            "context_json": "{}",
            "novelty_seed": "unique-seed",
        })
        assert "novel" in rendered.lower()


class TestPracticeFlashcardsGenerateAsset:
    """Tests for practice/practice_flashcards_generate_v1 prompt asset."""

    def test_asset_loads(self, registry: PromptRegistry) -> None:
        asset = registry.get("practice_practice_flashcards_generate_v1")
        assert asset is not None
        assert asset.meta.task_type == "practice"
        assert asset.meta.version == 1

    def test_asset_renders_with_all_placeholders(self, registry: PromptRegistry) -> None:
        rendered = registry.render("practice_practice_flashcards_generate_v1", {
            "card_count": "10",
            "context_json": '{"concept_name": "Mitosis"}',
        })
        assert "CARD_COUNT: 10" in rendered
        assert "Mitosis" in rendered

    def test_asset_contains_json_output_contract(self, registry: PromptRegistry) -> None:
        rendered = registry.render("practice_practice_flashcards_generate_v1", {
            "card_count": "5",
            "context_json": "{}",
        })
        assert "flashcards" in rendered
        assert "front" in rendered
        assert "back" in rendered
        assert "hint" in rendered

    def test_asset_grounded_in_source(self, registry: PromptRegistry) -> None:
        rendered = registry.render("practice_practice_flashcards_generate_v1", {
            "card_count": "5",
            "context_json": "{}",
        })
        assert "source" in rendered.lower() or "concept" in rendered.lower()
