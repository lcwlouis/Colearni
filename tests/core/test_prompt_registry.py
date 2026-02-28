"""Tests for prompt registry and renderer."""

from __future__ import annotations

from pathlib import Path

import pytest
from core.prompting.loader import PromptLoadError
from core.prompting.models import PromptAsset, PromptMeta, TaskType
from core.prompting.registry import PromptRegistry
from core.prompting.renderer import PromptRenderError, render

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "core" / "prompting" / "assets"


# ── Renderer Tests ───────────────────────────────────────────────────


class TestRender:
    """Test placeholder rendering with strict missing-key failures."""

    def _make_asset(self, template: str) -> PromptAsset:
        meta = PromptMeta(
            prompt_id="test_v1", task_type=TaskType.TUTOR, version=1
        )
        import re
        placeholders = frozenset(
            re.findall(r"(?<!\{)\{([a-z_][a-z0-9_]*)\}(?!\})", template)
        )
        return PromptAsset(meta=meta, template=template, placeholders=placeholders)

    def test_render_basic(self) -> None:
        asset = self._make_asset("Hello {name}, topic is {topic}.")
        result = render(asset, {"name": "Alice", "topic": "DNA"})
        assert result == "Hello Alice, topic is DNA."

    def test_render_missing_placeholder_raises(self) -> None:
        asset = self._make_asset("Hello {name}, topic is {topic}.")
        with pytest.raises(PromptRenderError, match="Missing placeholders"):
            render(asset, {"name": "Alice"})

    def test_render_extra_context_ignored(self) -> None:
        asset = self._make_asset("Hello {name}.")
        result = render(asset, {"name": "Alice", "extra": "ignored"})
        assert result == "Hello Alice."

    def test_render_none_value_becomes_empty(self) -> None:
        asset = self._make_asset("Summary: {summary}")
        result = render(asset, {"summary": None})
        assert result == "Summary: "

    def test_render_no_placeholders(self) -> None:
        asset = self._make_asset("Static prompt with no slots.")
        result = render(asset, {})
        assert result == "Static prompt with no slots."

    def test_render_preserves_escaped_braces(self) -> None:
        asset = self._make_asset("JSON: {{\"key\": \"{value}\"}}")
        result = render(asset, {"value": "42"})
        assert "{{" in result  # escaped braces stay
        assert "42" in result


# ── Registry Tests ───────────────────────────────────────────────────


class TestPromptRegistry:
    """Test the prompt registry: load, cache, render, list."""

    def test_get_existing_prompt(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        asset = reg.get("tutor_socratic_v1")
        assert asset.meta.prompt_id == "tutor_socratic_v1"

    def test_get_caches_asset(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        a1 = reg.get("tutor_socratic_v1")
        a2 = reg.get("tutor_socratic_v1")
        assert a1 is a2

    def test_get_missing_raises(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        with pytest.raises(PromptLoadError):
            reg.get("nonexistent_v99")

    def test_render_end_to_end(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        ctx = {
            "strict_grounded_mode": "true",
            "mastery_status": "unlocked",
            "document_summaries": "Doc A summary",
            "assessment_context": "Topic: DNA, score: 80%",
            "flashcard_progress": "5/10 mastered",
            "history_summary": "User asked about DNA replication",
            "evidence_block": "e1: DNA is a double helix",
            "query": "How does DNA replicate?",
        }
        result = reg.render("tutor_socratic_v1", ctx)
        assert "How does DNA replicate?" in result
        assert "study partner" in result.lower()
        assert "e1: DNA is a double helix" in result

    def test_render_missing_placeholder_raises(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        with pytest.raises(PromptRenderError):
            reg.render("tutor_socratic_v1", {"query": "test"})

    def test_meta_returns_metadata(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        meta = reg.meta("tutor_socratic_v1")
        assert meta.task_type == TaskType.TUTOR
        assert meta.version == 1
        assert meta.output_format == "markdown"

    def test_list_ids(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        ids = reg.list_ids()
        assert "tutor_socratic_v1" in ids
        assert "tutor_direct_v1" in ids

    def test_invalidate_single(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        reg.get("tutor_socratic_v1")
        assert "tutor_socratic_v1" in reg._cache
        reg.invalidate("tutor_socratic_v1")
        assert "tutor_socratic_v1" not in reg._cache

    def test_invalidate_all(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        reg.get("tutor_socratic_v1")
        reg.get("tutor_direct_v1")
        assert len(reg._cache) == 2
        reg.invalidate()
        assert len(reg._cache) == 0

    def test_by_task_filters(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        reg.get("tutor_socratic_v1")
        reg.get("tutor_direct_v1")
        tutor_ids = reg.by_task(TaskType.TUTOR)
        assert set(tutor_ids) == {"tutor_socratic_v1", "tutor_direct_v1"}
        graph_ids = reg.by_task(TaskType.GRAPH)
        assert graph_ids == []

    def test_from_tmp_dir(self, tmp_path: Path) -> None:
        (tmp_path / "mini_v1.md").write_text(
            "task_type: tutor\nversion: 1\n\nHi {name}!",
            encoding="utf-8",
        )
        reg = PromptRegistry(assets_dir=tmp_path)
        result = reg.render("mini_v1", {"name": "Test"})
        assert result == "Hi Test!"
