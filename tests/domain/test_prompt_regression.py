"""P8: Prompt regression tests and snapshot harness.

These tests ensure:
1. All expected prompt IDs are discoverable.
2. Critical prompts contain required sections.
3. Repair prompt is loadable and renderable.
4. Observability metadata is accessible via render_with_meta.
"""

from __future__ import annotations

import pytest

from core.prompting import PromptRegistry


@pytest.fixture()
def registry() -> PromptRegistry:
    return PromptRegistry()


# ---- Prompt ID regression ----

EXPECTED_PROMPT_IDS = [
    "tutor_socratic_v1",
    "tutor_direct_v1",
    "routing_query_analyzer_v1",
    "graph_extract_chunk_v1",
    "graph_disambiguate_v1",
    "graph_merge_summary_v1",
    "graph_repair_json_v1",
    "assessment_levelup_generate_v1",
    "assessment_levelup_grade_v1",
    "practice_practice_quiz_generate_v1",
    "practice_practice_flashcards_generate_v1",
    "suggestion_suggestion_hook_v1",
    "document_document_summary_v1",
]


class TestPromptIdRegression:
    """Every expected prompt ID must be discoverable and loadable."""

    @pytest.mark.parametrize("prompt_id", EXPECTED_PROMPT_IDS)
    def test_prompt_id_loadable(self, registry: PromptRegistry, prompt_id: str) -> None:
        asset = registry.get(prompt_id)
        assert asset is not None
        assert asset.meta.prompt_id == prompt_id

    def test_all_expected_ids_discoverable(self, registry: PromptRegistry) -> None:
        discovered = set(registry.list_ids())
        for expected in EXPECTED_PROMPT_IDS:
            assert expected in discovered, f"Missing prompt ID: {expected}"


# ---- Required sections regression ----

REQUIRED_SECTIONS = {
    "tutor_socratic_v1": ["guiding question", "study partner"],
    "tutor_direct_v1": ["direct", "mastery"],
    "assessment_levelup_generate_v1": ["mastery", "item_type", "rubric_keywords"],
    "assessment_levelup_grade_v1": ["_generation_context", "score", "critical_misconception"],
    "graph_extract_chunk_v1": ["concept", "relationship"],
    "document_document_summary_v1": ["500", "plain text"],
    "suggestion_suggestion_hook_v1": ["do not choose", "hook"],
}


class TestRequiredSections:
    """Critical prompts must contain required sections/keywords."""

    @pytest.mark.parametrize(
        "prompt_id,required",
        list(REQUIRED_SECTIONS.items()),
        ids=list(REQUIRED_SECTIONS.keys()),
    )
    def test_required_sections_present(
        self,
        registry: PromptRegistry,
        prompt_id: str,
        required: list[str],
    ) -> None:
        asset = registry.get(prompt_id)
        lower = asset.template.lower()
        for section in required:
            assert section.lower() in lower, (
                f"Prompt {prompt_id} missing required section: {section!r}"
            )


# ---- Repair prompt ----

class TestRepairPrompt:
    """The JSON repair prompt must be loadable and renderable."""

    def test_repair_prompt_loads(self, registry: PromptRegistry) -> None:
        asset = registry.get("graph_repair_json_v1")
        assert asset.meta.task_type == "graph"
        assert asset.meta.output_format == "json"

    def test_repair_prompt_renders(self, registry: PromptRegistry) -> None:
        rendered = registry.render("graph_repair_json_v1", {
            "original_prompt_excerpt": "Extract concepts from...",
            "malformed_output": '{"concepts": [missing bracket',
            "error_message": "JSONDecodeError: Expecting value",
        })
        assert "missing bracket" in rendered
        assert "JSONDecodeError" in rendered

    def test_repair_prompt_bounded(self, registry: PromptRegistry) -> None:
        asset = registry.get("graph_repair_json_v1")
        # Repair prompt should not encourage infinite retries
        lower = asset.template.lower()
        assert "fabricate" in lower or "preserve" in lower


# ---- Observability metadata ----

class TestObservabilityMetadata:
    """render_with_meta must return usable observability data."""

    def test_render_with_meta_returns_tuple(self, registry: PromptRegistry) -> None:
        rendered, meta = registry.render_with_meta("tutor_socratic_v1", {
            "mastery_status": "learning",
            "evidence_block": "Watson and Crick discovered...",
            "assessment_context": "",
            "document_summaries": "",
            "flashcard_progress": "",
            "history_summary": "Student asked about genetics",
            "strict_grounded_mode": "false",
            "query": "What is DNA?",
        })
        assert isinstance(rendered, str)
        assert len(rendered) > 0
        assert meta.prompt_id == "tutor_socratic_v1"
        assert meta.version == 1
        assert meta.task_type == "tutor"

    def test_observability_fields_present(self, registry: PromptRegistry) -> None:
        _, meta = registry.render_with_meta("assessment_levelup_grade_v1", {
            "item_ids_json": "[1]",
            "quiz_submission_json": "[]",
        })
        # All fields needed for span/log emission
        assert meta.prompt_id
        assert meta.version >= 1
        assert meta.task_type
        assert meta.output_format in ("markdown", "json", "text")


# ---- Snapshot regression: critical prompt lengths ----

PROMPT_LENGTH_BOUNDS = {
    "tutor_socratic_v1": (100, 5000),
    "tutor_direct_v1": (100, 5000),
    "assessment_levelup_generate_v1": (200, 5000),
    "assessment_levelup_grade_v1": (100, 3000),
    "document_document_summary_v1": (100, 2000),
}


class TestPromptLengthSnapshot:
    """Prompt template lengths must stay within expected bounds."""

    @pytest.mark.parametrize(
        "prompt_id,bounds",
        list(PROMPT_LENGTH_BOUNDS.items()),
        ids=list(PROMPT_LENGTH_BOUNDS.keys()),
    )
    def test_template_length_in_bounds(
        self,
        registry: PromptRegistry,
        prompt_id: str,
        bounds: tuple[int, int],
    ) -> None:
        asset = registry.get(prompt_id)
        min_len, max_len = bounds
        actual = len(asset.template)
        assert min_len <= actual <= max_len, (
            f"Prompt {prompt_id} template length {actual} outside bounds [{min_len}, {max_len}]"
        )
