"""Tests for batch graph extraction (L7.1)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from core.contracts import GraphLLMClient
from core.llm_messages import Message
from domain.graph.extraction import (
    batch_extract_raw_graph_from_chunks,
    extract_raw_graph_from_chunk,
)


# ── Stub LLM client ──────────────────────────────────────────────────

class _StubLLM:
    """Returns canned payloads keyed by chunk text."""

    def __init__(self, payloads: dict[str, dict[str, Any]]) -> None:
        self._payloads = payloads
        self.call_count = 0

    def extract_raw_graph(self, *, chunk_text: str) -> Mapping[str, Any]:
        self.call_count += 1
        return self._payloads.get(chunk_text, {"concepts": [], "edges": []})

    def batch_extract_raw_graph(
        self, *, chunk_texts: Sequence[str]
    ) -> Sequence[Mapping[str, Any]]:
        self.call_count += 1
        return [self._payloads.get(ct, {"concepts": [], "edges": []}) for ct in chunk_texts]

    def disambiguate(self, **kw: Any) -> Mapping[str, Any]:
        return {"decision": "CREATE_NEW", "confidence": 1.0}

    def disambiguate_batch(self, **kw: Any) -> Sequence[Mapping[str, Any]]:
        return []

    def generate_tutor_text(self, **kw: Any) -> str:
        return ""

    async def async_complete_messages(self, *a: Any, **kw: Any) -> tuple[str, Any]:
        return "", None

    async def async_complete_messages_json(self, *a: Any, **kw: Any) -> dict[str, Any]:
        return {}


_PAYLOAD_A: dict[str, Any] = {
    "concepts": [
        {"name": "Algebra", "context_snippet": "intro to algebra", "description": "math", "tier": "topic"},
    ],
    "edges": [],
}

_PAYLOAD_B: dict[str, Any] = {
    "concepts": [
        {"name": "Geometry", "context_snippet": "shapes", "description": "spatial math", "tier": "topic"},
    ],
    "edges": [
        {
            "src_name": "Geometry",
            "tgt_name": "Algebra",
            "relation_type": "related_to",
            "description": "both math",
            "keywords": ["math"],
            "weight": 5,
        },
    ],
}


# ── Tests ──────────────────────────────────────────────────────────

def test_batch_extract_returns_correct_count() -> None:
    llm = _StubLLM({"chunk_a": _PAYLOAD_A, "chunk_b": _PAYLOAD_B})
    results = batch_extract_raw_graph_from_chunks(
        llm_client=llm,
        chunk_texts=["chunk_a", "chunk_b"],
        concept_description_max_chars=200,
        edge_description_max_chars=200,
    )
    assert len(results) == 2
    assert len(results[0].concepts) == 1
    assert results[0].concepts[0].name == "Algebra"
    assert len(results[1].concepts) == 1
    assert results[1].concepts[0].name == "Geometry"
    assert len(results[1].edges) == 1


def test_batch_extract_empty_input() -> None:
    llm = _StubLLM({})
    results = batch_extract_raw_graph_from_chunks(
        llm_client=llm,
        chunk_texts=[],
        concept_description_max_chars=200,
        edge_description_max_chars=200,
    )
    assert results == []
    assert llm.call_count == 0


def test_batch_extract_handles_validation_failure() -> None:
    """Invalid payload for one chunk should produce empty extraction, not crash."""
    bad_payload: dict[str, Any] = {"concepts": "not_a_list", "edges": []}

    class _BadBatchLLM(_StubLLM):
        def batch_extract_raw_graph(
            self, *, chunk_texts: Sequence[str]
        ) -> Sequence[Mapping[str, Any]]:
            return [bad_payload, _PAYLOAD_A]

    llm = _BadBatchLLM({})
    results = batch_extract_raw_graph_from_chunks(
        llm_client=llm,
        chunk_texts=["bad_chunk", "good_chunk"],
        concept_description_max_chars=200,
        edge_description_max_chars=200,
    )
    assert len(results) == 2
    assert results[0].concepts == []
    assert results[0].edges == []
    assert len(results[1].concepts) == 1


def test_batch_extract_preserves_normalization() -> None:
    """Batch should apply same dedup/normalization as single extraction."""
    dup_payload: dict[str, Any] = {
        "concepts": [
            {"name": "Vector Space", "context_snippet": "vec", "description": "short", "tier": "topic"},
            {"name": "  vector   space  ", "context_snippet": "vec", "description": "a longer description wins", "tier": "granular"},
        ],
        "edges": [],
    }
    llm = _StubLLM({"chunk": dup_payload})
    results = batch_extract_raw_graph_from_chunks(
        llm_client=llm,
        chunk_texts=["chunk"],
        concept_description_max_chars=200,
        edge_description_max_chars=200,
    )
    assert len(results) == 1
    assert len(results[0].concepts) == 1
    assert results[0].concepts[0].description == "a longer description wins"


def test_single_and_batch_produce_same_result() -> None:
    """Single extraction and batch extraction should produce identical output."""
    llm = _StubLLM({"chunk_a": _PAYLOAD_A})
    single = extract_raw_graph_from_chunk(
        llm_client=llm,
        chunk_text="chunk_a",
        concept_description_max_chars=200,
        edge_description_max_chars=200,
    )
    batch = batch_extract_raw_graph_from_chunks(
        llm_client=llm,
        chunk_texts=["chunk_a"],
        concept_description_max_chars=200,
        edge_description_max_chars=200,
    )
    assert len(batch) == 1
    assert batch[0].concepts == single.concepts
    assert batch[0].edges == single.edges
