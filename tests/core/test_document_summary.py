"""Tests for P7: Document summary prompt asset."""

from __future__ import annotations

import pytest

from core.prompting import PromptRegistry


@pytest.fixture()
def registry() -> PromptRegistry:
    return PromptRegistry()


class TestDocumentSummaryAsset:
    """Tests for document/document_summary_v1 prompt asset."""

    def test_asset_loads(self, registry: PromptRegistry) -> None:
        asset = registry.get("document_document_summary_v1")
        assert asset is not None
        assert asset.meta.task_type == "document"
        assert asset.meta.version == 1
        assert asset.meta.output_format == "text"

    def test_asset_renders_with_chunks(self, registry: PromptRegistry) -> None:
        rendered = registry.render("document_document_summary_v1", {
            "chunks": "Chapter 1: Introduction to Biology\n\nChapter 2: Cells",
        })
        assert "Introduction to Biology" in rendered
        assert "Cells" in rendered

    def test_system_asset_loads(self, registry: PromptRegistry) -> None:
        asset = registry.get("document_document_summary_v1_system")
        assert asset is not None
        assert asset.meta.task_type == "document"
        assert asset.meta.version == 1

    def test_system_asset_enforces_length_bound(self, registry: PromptRegistry) -> None:
        rendered = registry.render("document_document_summary_v1_system", {})
        assert "500" in rendered or "2 or 3 sentences" in rendered

    def test_system_asset_grounded_no_outside_knowledge(self, registry: PromptRegistry) -> None:
        rendered = registry.render("document_document_summary_v1_system", {})
        lower = rendered.lower()
        assert "outside knowledge" in lower or "only the supplied" in lower

    def test_system_asset_plain_text_output(self, registry: PromptRegistry) -> None:
        rendered = registry.render("document_document_summary_v1_system", {})
        assert "plain text" in rendered.lower()
