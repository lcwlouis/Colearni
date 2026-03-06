"""Tests for P6: Practice prompt asset migration."""

from __future__ import annotations

import pytest

from core.prompting import PromptRegistry


@pytest.fixture()
def registry() -> PromptRegistry:
    return PromptRegistry()


class TestPracticeQuizGenerateSystemAsset:
    """Tests for practice/practice_quiz_generate_v1_system prompt asset."""

    def test_system_asset_loads(self, registry: PromptRegistry) -> None:
        asset = registry.get("practice_practice_quiz_generate_v1_system")
        assert asset is not None
        assert asset.meta.task_type == "practice"

    def test_system_asset_contains_output_contract(self, registry: PromptRegistry) -> None:
        rendered = registry.render("practice_practice_quiz_generate_v1_system", {})
        assert "item_type" in rendered
        assert "short_answer" in rendered
        assert "mcq" in rendered
        assert "rubric_keywords" in rendered

    def test_system_asset_contains_role_and_rules(self, registry: PromptRegistry) -> None:
        rendered = registry.render("practice_practice_quiz_generate_v1_system", {})
        assert "novel" in rendered.lower()
        assert "Return valid JSON only" in rendered


class TestPracticeQuizGenerateAsset:
    """Tests for practice/practice_quiz_generate_v1 prompt asset (user prompt)."""

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
            "source_excerpts": "- Plants convert sunlight to energy",
        })
        assert "QUESTION_COUNT: 7" in rendered
        assert "Photosynthesis" in rendered
        assert "abc-123" in rendered

    def test_asset_includes_source_material(self, registry: PromptRegistry) -> None:
        rendered = registry.render("practice_practice_quiz_generate_v1", {
            "question_count": "5",
            "context_json": "{}",
            "novelty_seed": "x",
            "source_excerpts": "- Chloroplasts absorb light",
        })
        assert "Chloroplasts absorb light" in rendered
        assert "Source material" in rendered


class TestPracticeFlashcardsGenerateSystemAsset:
    """Tests for practice/practice_flashcards_generate_v1_system prompt asset."""

    def test_system_asset_loads(self, registry: PromptRegistry) -> None:
        asset = registry.get("practice_practice_flashcards_generate_v1_system")
        assert asset is not None
        assert asset.meta.task_type == "practice"

    def test_system_asset_contains_output_contract(self, registry: PromptRegistry) -> None:
        rendered = registry.render("practice_practice_flashcards_generate_v1_system", {})
        assert "flashcards" in rendered
        assert "front" in rendered
        assert "back" in rendered
        assert "hint" in rendered

    def test_system_asset_contains_dedup_rule(self, registry: PromptRegistry) -> None:
        rendered = registry.render("practice_practice_flashcards_generate_v1_system", {})
        assert "do not" in rendered.lower()


class TestPracticeFlashcardsGenerateAsset:
    """Tests for practice/practice_flashcards_generate_v1 prompt asset (user prompt)."""

    def test_asset_loads(self, registry: PromptRegistry) -> None:
        asset = registry.get("practice_practice_flashcards_generate_v1")
        assert asset is not None
        assert asset.meta.task_type == "practice"
        assert asset.meta.version == 1

    def test_asset_renders_with_all_placeholders(self, registry: PromptRegistry) -> None:
        rendered = registry.render("practice_practice_flashcards_generate_v1", {
            "card_count": "10",
            "context_json": '{"concept_name": "Mitosis"}',
            "existing_flashcards_text": "- Q: What is mitosis?  A: Cell division",
            "source_excerpts": "- Cells divide during mitosis",
        })
        assert "CARD_COUNT: 10" in rendered
        assert "Mitosis" in rendered
        assert "What is mitosis?" in rendered

    def test_asset_includes_source_material(self, registry: PromptRegistry) -> None:
        rendered = registry.render("practice_practice_flashcards_generate_v1", {
            "card_count": "5",
            "context_json": "{}",
            "existing_flashcards_text": "None yet.",
            "source_excerpts": "- DNA replicates before division",
        })
        assert "DNA replicates before division" in rendered
        assert "Source material" in rendered

    def test_asset_includes_existing_flashcards_dedup(self, registry: PromptRegistry) -> None:
        rendered = registry.render("practice_practice_flashcards_generate_v1", {
            "card_count": "5",
            "context_json": "{}",
            "existing_flashcards_text": "- Q: What is X?  A: X is Y",
            "source_excerpts": "(none)",
        })
        assert "do not duplicate" in rendered.lower()
        assert "What is X?" in rendered
