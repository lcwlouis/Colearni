"""Tests for graph LLM provider prompt rendering via assets."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from typing import Any

from adapters.llm.providers import _BaseGraphLLMClient


class _StubGraphLLMClient(_BaseGraphLLMClient):
    """Minimal stub to test prompt rendering without a real SDK."""

    def __init__(self, *, response: dict[str, Any]) -> None:
        super().__init__(
            model="test-model",
            timeout_seconds=30.0,
            provider="stub",
        )
        self._response = response

    def _sdk_call(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, object] | None,
    ) -> Mapping[str, Any]:
        # Capture the prompt for assertion
        self._last_messages = messages
        return {
            "choices": [
                {"message": {"content": json.dumps(self._response)}}
            ],
        }

    def _sdk_stream_call(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> Iterator[Mapping[str, Any]]:
        return iter([])


class TestExtractRawGraphPrompt:
    """Test that extract_raw_graph uses the asset-backed prompt."""

    def test_prompt_contains_chunk_text(self) -> None:
        client = _StubGraphLLMClient(
            response={"concepts": [], "edges": []}
        )
        client.extract_raw_graph(chunk_text="Photosynthesis is the process")
        user_msg = client._last_messages[-1]["content"]
        assert "Photosynthesis is the process" in user_msg

    def test_prompt_uses_asset_structure(self) -> None:
        client = _StubGraphLLMClient(
            response={"concepts": [], "edges": []}
        )
        client.extract_raw_graph(chunk_text="test chunk")
        system_msg = client._last_messages[0]["content"]
        user_msg = client._last_messages[-1]["content"]
        # System message should have the extraction instructions
        assert "knowledge graph" in system_msg.lower()
        # User message should contain the chunk text
        assert "test chunk" in user_msg

    def test_empty_extraction_returns_empty(self) -> None:
        client = _StubGraphLLMClient(
            response={"concepts": [], "edges": []}
        )
        result = client.extract_raw_graph(chunk_text="nothing useful here")
        assert result["concepts"] == []
        assert result["edges"] == []


class TestDisambiguatePrompt:
    """Test that disambiguate uses the asset-backed prompt."""

    def test_prompt_contains_raw_name(self) -> None:
        client = _StubGraphLLMClient(
            response={
                "decision": "CREATE_NEW",
                "confidence": 0.5,
                "merge_into_id": None,
                "alias_to_add": None,
                "proposed_description": None,
            }
        )
        client.disambiguate(
            raw_name="DNA replication",
            context_snippet="copying DNA",
            candidates=[{"id": 1, "canonical_name": "DNA Replication"}],
        )
        user_msg = client._last_messages[-1]["content"]
        assert "DNA replication" in user_msg

    def test_prompt_contains_candidates(self) -> None:
        client = _StubGraphLLMClient(
            response={
                "decision": "MERGE_INTO",
                "confidence": 0.95,
                "merge_into_id": 1,
                "alias_to_add": "dna replication",
                "proposed_description": "DNA copying",
            }
        )
        client.disambiguate(
            raw_name="DNA replication",
            context_snippet=None,
            candidates=[{"id": 1, "canonical_name": "DNA Replication"}],
        )
        user_msg = client._last_messages[-1]["content"]
        assert "DNA Replication" in user_msg

    def test_create_new_bias_in_prompt(self) -> None:
        """Asset system prompt should mention CREATE_NEW as the safe default."""
        client = _StubGraphLLMClient(
            response={
                "decision": "CREATE_NEW",
                "confidence": 0.3,
                "merge_into_id": None,
                "alias_to_add": None,
                "proposed_description": None,
            }
        )
        client.disambiguate(
            raw_name="test",
            context_snippet="test",
            candidates=[],
        )
        system_msg = client._last_messages[0]["content"]
        assert "CREATE_NEW" in system_msg
