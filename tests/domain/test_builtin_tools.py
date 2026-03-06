"""Tests for domain.tools — built-in tool implementations."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from core.tools import ToolRegistry
from domain.tools.check_mastery import CheckMasteryTool
from domain.tools.lookup_concept import LookupConceptTool
from domain.tools.search_knowledge import SearchKnowledgeTool


# ---------------------------------------------------------------------------
# SearchKnowledgeTool
# ---------------------------------------------------------------------------


class TestSearchKnowledgeTool:
    def _make_tool(self, results: list | None = None) -> SearchKnowledgeTool:
        def mock_retrieve(*, query: str, workspace_id: int, top_k: int):
            if results is None:
                return []
            return results

        return SearchKnowledgeTool(retrieve_fn=mock_retrieve, workspace_id=1)

    @pytest.mark.anyio
    async def test_returns_results(self):
        chunk = MagicMock()
        chunk.text = "Photosynthesis converts light energy"
        chunk.score = 0.95
        chunk.document_title = "Biology 101"
        tool = self._make_tool([chunk])

        result = json.loads(await tool.execute(query="photosynthesis"))
        assert result["count"] == 1
        assert result["results"][0]["text"] == "Photosynthesis converts light energy"
        assert result["results"][0]["score"] == 0.95
        assert result["results"][0]["source"] == "Biology 101"

    @pytest.mark.anyio
    async def test_empty_results(self):
        tool = self._make_tool([])
        result = json.loads(await tool.execute(query="nonexistent"))
        assert result["count"] == 0
        assert result["results"] == []

    @pytest.mark.anyio
    async def test_custom_top_k(self):
        calls: list[dict] = []

        def mock_retrieve(*, query: str, workspace_id: int, top_k: int):
            calls.append({"query": query, "top_k": top_k})
            return []

        tool = SearchKnowledgeTool(retrieve_fn=mock_retrieve, workspace_id=1)
        await tool.execute(query="test", top_k=10)
        assert calls[0]["top_k"] == 10

    def test_protocol_compliance(self):
        tool = self._make_tool()
        assert tool.name == "search_knowledge_base"
        assert tool.description
        assert tool.parameters_model

    def test_registers_in_registry(self):
        registry = ToolRegistry()
        registry.register(self._make_tool())
        specs = registry.to_openai_tools()
        assert specs[0]["function"]["name"] == "search_knowledge_base"


# ---------------------------------------------------------------------------
# LookupConceptTool
# ---------------------------------------------------------------------------


class TestLookupConceptTool:
    def _make_tool(
        self, detail: dict | None = None, error: Exception | None = None,
    ) -> LookupConceptTool:
        def mock_lookup(session: Any, *, workspace_id: int, concept_id: int):
            if error:
                raise error
            return detail or {}

        return LookupConceptTool(
            lookup_fn=mock_lookup, session=MagicMock(), workspace_id=1,
        )

    @pytest.mark.anyio
    async def test_returns_concept_detail(self):
        tool = self._make_tool(detail={
            "canonical_name": "Photosynthesis",
            "description": "Process of converting light to energy",
            "aliases": ["photo synthesis"],
            "tier": "topic",
        })
        result = json.loads(await tool.execute(concept_id=42))
        assert result["name"] == "Photosynthesis"
        assert result["description"] == "Process of converting light to energy"
        assert result["aliases"] == ["photo synthesis"]
        assert result["tier"] == "topic"
        assert result["concept_id"] == 42

    @pytest.mark.anyio
    async def test_concept_not_found(self):
        tool = self._make_tool(error=ValueError("Not found"))
        result = json.loads(await tool.execute(concept_id=999))
        assert "error" in result
        assert "Not found" in result["error"]

    def test_protocol_compliance(self):
        tool = self._make_tool()
        assert tool.name == "lookup_concept"
        assert tool.description
        assert tool.parameters_model


# ---------------------------------------------------------------------------
# CheckMasteryTool
# ---------------------------------------------------------------------------


class TestCheckMasteryTool:
    def _make_tool(self, mastery: dict | None = None) -> CheckMasteryTool:
        def mock_mastery(
            session: Any, *, workspace_id: int, user_id: int, concept_id: int,
        ):
            return mastery

        return CheckMasteryTool(
            mastery_fn=mock_mastery,
            session=MagicMock(),
            workspace_id=1,
            user_id=42,
        )

    @pytest.mark.anyio
    async def test_learned_concept(self):
        tool = self._make_tool({"status": "learned", "score": 0.9})
        result = json.loads(await tool.execute(concept_id=5))
        assert result["status"] == "learned"
        assert result["score"] == 0.9
        assert result["concept_id"] == 5

    @pytest.mark.anyio
    async def test_not_started_concept(self):
        tool = self._make_tool(None)
        result = json.loads(await tool.execute(concept_id=5))
        assert result["status"] == "not_started"
        assert result["score"] == 0.0

    @pytest.mark.anyio
    async def test_learning_concept(self):
        tool = self._make_tool({"status": "learning", "score": 0.5})
        result = json.loads(await tool.execute(concept_id=5))
        assert result["status"] == "learning"
        assert result["score"] == 0.5

    def test_protocol_compliance(self):
        tool = self._make_tool()
        assert tool.name == "check_mastery"
        assert tool.description
        assert tool.parameters_model


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


class TestToolRegistryIntegration:
    def test_all_three_tools_register(self):
        registry = ToolRegistry()
        registry.register(SearchKnowledgeTool(
            retrieve_fn=lambda **_: [], workspace_id=1,
        ))
        registry.register(LookupConceptTool(
            lookup_fn=lambda *a, **k: {}, session=None, workspace_id=1,
        ))
        registry.register(CheckMasteryTool(
            mastery_fn=lambda *a, **k: None, session=None,
            workspace_id=1, user_id=1,
        ))
        assert len(registry) == 3
        specs = registry.to_openai_tools()
        names = {s["function"]["name"] for s in specs}
        assert names == {"search_knowledge_base", "lookup_concept", "check_mastery"}


# ---------------------------------------------------------------------------
# Registry factory
# ---------------------------------------------------------------------------


class TestRegistryFactory:
    def test_all_deps_provided(self):
        from domain.tools.registry_factory import build_tool_registry

        registry = build_tool_registry(
            session=None,
            workspace_id=1,
            user_id=1,
            retrieve_fn=lambda **_: [],
            concept_lookup_fn=lambda *a, **k: {},
            mastery_fn=lambda *a, **k: None,
            web_search_api_key="test-key",
        )
        assert len(registry) == 4
        assert "web_search" in registry

    def test_all_deps_without_web_search(self):
        from domain.tools.registry_factory import build_tool_registry

        registry = build_tool_registry(
            session=None,
            workspace_id=1,
            user_id=1,
            retrieve_fn=lambda **_: [],
            concept_lookup_fn=lambda *a, **k: {},
            mastery_fn=lambda *a, **k: None,
        )
        assert len(registry) == 3
        assert "web_search" not in registry

    def test_partial_deps(self):
        from domain.tools.registry_factory import build_tool_registry

        registry = build_tool_registry(
            session=None,
            workspace_id=1,
            user_id=1,
            retrieve_fn=lambda **_: [],
        )
        assert len(registry) == 1
        assert "search_knowledge_base" in registry

    def test_no_deps(self):
        from domain.tools.registry_factory import build_tool_registry

        registry = build_tool_registry(
            session=None,
            workspace_id=1,
            user_id=1,
        )
        assert len(registry) == 0
