"""Tests for graph prompt assets – loading, rendering, and contract validation."""

from __future__ import annotations

from pathlib import Path

from core.prompting import PromptRegistry
from core.prompting.models import TaskType

ASSETS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "core" / "prompting" / "assets"


class TestGraphExtractChunkAsset:
    """Test the graph_extract_chunk_v1 prompt asset."""

    def test_loads_successfully(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        asset = reg.get("graph_extract_chunk_v1")
        assert asset.meta.task_type == TaskType.GRAPH
        assert asset.meta.output_format == "json"
        assert asset.meta.version == 1

    def test_renders_with_chunk(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        result = reg.render("graph_extract_chunk_v1", {
            "chunk_text": "DNA is a double helix structure discovered by Watson and Crick."
        })
        assert "DNA is a double helix" in result
        assert "concepts" in result
        assert "edges" in result

    def test_placeholder_is_chunk_text(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        asset = reg.get("graph_extract_chunk_v1")
        assert "chunk_text" in asset.placeholders

    def test_empty_chunk_renders(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        result = reg.render("graph_extract_chunk_v1", {"chunk_text": ""})
        assert "CHUNK:" in result


class TestGraphDisambiguateAsset:
    """Test the graph_disambiguate_v1 prompt asset."""

    def test_loads_successfully(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        asset = reg.get("graph_disambiguate_v1")
        assert asset.meta.task_type == TaskType.GRAPH
        assert asset.meta.output_format == "json"

    def test_renders_with_inputs(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        result = reg.render("graph_disambiguate_v1", {
            "raw_name": "DNA replication",
            "context_snippet": "The process by which DNA copies itself.",
            "candidates_json": '[{"id": 1, "name": "DNA Replication"}]',
        })
        assert "DNA replication" in result
        assert "CREATE_NEW" in result
        assert "MERGE_INTO" in result

    def test_placeholders(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        asset = reg.get("graph_disambiguate_v1")
        assert asset.placeholders == frozenset({"raw_name", "context_snippet", "candidates_json"})


class TestGraphMergeSummaryAsset:
    """Test the graph_merge_summary_v1 prompt asset."""

    def test_loads_successfully(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        asset = reg.get("graph_merge_summary_v1")
        assert asset.meta.task_type == TaskType.GRAPH
        assert asset.meta.output_format == "json"

    def test_renders_with_cluster(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        result = reg.render("graph_merge_summary_v1", {
            "reference_json": '{"id": 1, "name": "Photosynthesis"}',
            "cluster_members_json": '[{"id": 2, "name": "Photo synthesis"}]',
        })
        assert "Photosynthesis" in result
        assert "should_merge" in result

    def test_placeholders(self) -> None:
        reg = PromptRegistry(assets_dir=ASSETS_DIR)
        asset = reg.get("graph_merge_summary_v1")
        assert asset.placeholders == frozenset({"reference_json", "cluster_members_json"})
