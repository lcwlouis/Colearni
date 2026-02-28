"""Tests for P7: Suggestion prompt asset."""

from __future__ import annotations

import pytest

from core.prompting import PromptRegistry


@pytest.fixture()
def registry() -> PromptRegistry:
    return PromptRegistry()


class TestSuggestionHookAsset:
    """Tests for suggestion/suggestion_hook_v1 prompt asset."""

    def test_asset_loads(self, registry: PromptRegistry) -> None:
        asset = registry.get("suggestion_suggestion_hook_v1")
        assert asset is not None
        assert asset.meta.task_type == "suggestion"
        assert asset.meta.version == 1
        assert asset.meta.output_format == "json"

    def test_asset_renders_with_all_placeholders(self, registry: PromptRegistry) -> None:
        rendered = registry.render("suggestion_suggestion_hook_v1", {
            "selection_mode": "curiosity",
            "concept_json": '{"name": "Photosynthesis"}',
            "adjacent_context_json": '{"related": ["Respiration"]}',
            "learner_context_json": '{"level": "beginner"}',
        })
        assert "curiosity" in rendered
        assert "Photosynthesis" in rendered
        assert "Respiration" in rendered
        assert "beginner" in rendered

    def test_asset_does_not_choose_concept(self, registry: PromptRegistry) -> None:
        rendered = registry.render("suggestion_suggestion_hook_v1", {
            "selection_mode": "x",
            "concept_json": "{}",
            "adjacent_context_json": "{}",
            "learner_context_json": "{}",
        })
        assert "do not choose" in rendered.lower()

    def test_asset_contains_json_output_contract(self, registry: PromptRegistry) -> None:
        rendered = registry.render("suggestion_suggestion_hook_v1", {
            "selection_mode": "x",
            "concept_json": "{}",
            "adjacent_context_json": "{}",
            "learner_context_json": "{}",
        })
        assert "title" in rendered
        assert "hook" in rendered
        assert "why_now" in rendered
        assert "next_step" in rendered

    def test_asset_grounded_in_supplied_context(self, registry: PromptRegistry) -> None:
        rendered = registry.render("suggestion_suggestion_hook_v1", {
            "selection_mode": "x",
            "concept_json": "{}",
            "adjacent_context_json": "{}",
            "learner_context_json": "{}",
        })
        lower = rendered.lower()
        assert "supplied" in lower or "graph" in lower or "context" in lower
