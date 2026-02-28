"""Tests for prompt asset loader."""

from __future__ import annotations

from pathlib import Path

import pytest
from core.prompting.loader import PromptLoadError, list_assets, load_asset
from core.prompting.models import TaskType

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "core" / "prompting" / "assets"


class TestLoadAsset:
    """Test loading prompt assets from disk."""

    def test_load_existing_asset(self) -> None:
        asset = load_asset("tutor_socratic_v1", assets_dir=ASSETS_DIR)
        assert asset.meta.prompt_id == "tutor_socratic_v1"
        assert asset.meta.task_type == TaskType.TUTOR
        assert asset.meta.version == 1
        assert asset.meta.output_format == "markdown"
        assert "Socratic" in asset.template

    def test_load_direct_asset(self) -> None:
        asset = load_asset("tutor_direct_v1", assets_dir=ASSETS_DIR)
        assert asset.meta.prompt_id == "tutor_direct_v1"
        assert asset.meta.task_type == TaskType.TUTOR
        assert asset.meta.version == 1

    def test_missing_asset_raises(self) -> None:
        with pytest.raises(PromptLoadError, match="not found"):
            load_asset("nonexistent_v1", assets_dir=ASSETS_DIR)

    def test_detects_placeholders(self) -> None:
        asset = load_asset("tutor_socratic_v1", assets_dir=ASSETS_DIR)
        assert "query" in asset.placeholders
        assert "evidence_block" in asset.placeholders
        assert "strict_grounded_mode" in asset.placeholders

    def test_front_matter_parsed(self) -> None:
        asset = load_asset("tutor_socratic_v1", assets_dir=ASSETS_DIR)
        assert asset.meta.description != ""
        assert asset.meta.task_type == TaskType.TUTOR


class TestLoadAssetFromTmpDir:
    """Test loading from a custom directory with a minimal asset."""

    def test_load_flat_file(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "test_prompt_v1.md"
        prompt_file.write_text(
            "task_type: tutor\nversion: 1\n\nHello {name}, welcome to {topic}.",
            encoding="utf-8",
        )
        asset = load_asset("test_prompt_v1", assets_dir=tmp_path)
        assert asset.meta.prompt_id == "test_prompt_v1"
        assert asset.placeholders == frozenset({"name", "topic"})

    def test_no_placeholders(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "static_v1.md"
        prompt_file.write_text(
            "task_type: tutor\nversion: 1\n\nThis is a static prompt with no slots.",
            encoding="utf-8",
        )
        asset = load_asset("static_v1", assets_dir=tmp_path)
        assert asset.placeholders == frozenset()

    def test_json_output_format(self, tmp_path: Path) -> None:
        prompt_file = tmp_path / "json_task_v1.md"
        prompt_file.write_text(
            "task_type: graph\nversion: 1\noutput_format: json\n\nExtract {data}.",
            encoding="utf-8",
        )
        asset = load_asset("json_task_v1", assets_dir=tmp_path)
        assert asset.meta.output_format == "json"
        assert asset.meta.task_type == TaskType.GRAPH


class TestListAssets:
    """Test asset discovery."""

    def test_lists_real_assets(self) -> None:
        ids = list_assets(assets_dir=ASSETS_DIR)
        assert len(ids) >= 2
        assert "tutor_socratic_v1" in ids
        assert "tutor_direct_v1" in ids

    def test_empty_dir(self, tmp_path: Path) -> None:
        ids = list_assets(assets_dir=tmp_path)
        assert ids == []
