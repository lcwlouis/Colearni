"""Unit tests for schema-first raw graph extraction."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from core.contracts import GraphLLMClient
from domain.graph.extraction import extract_raw_graph_from_chunk


class StubExtractionLLM(GraphLLMClient):
    """Simple extraction test double."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self._payload = payload

    def extract_raw_graph(self, *, chunk_text: str) -> Mapping[str, Any]:
        return self._payload

    def disambiguate(
        self,
        *,
        raw_name: str,
        context_snippet: str | None,
        candidates: Sequence[Mapping[str, object]],
    ) -> Mapping[str, Any]:
        return {"decision": "CREATE_NEW", "confidence": 1.0}


def test_extract_raw_graph_dedupes_and_normalizes_payload() -> None:
    """Extraction should dedupe concepts/edges and enforce text limits."""
    llm = StubExtractionLLM(
        {
            "concepts": [
                {
                    "name": "Vector Space",
                    "context_snippet": "A vector space is closed under addition.",
                    "description": "first",
                },
                {
                    "name": " vector   space ",
                    "context_snippet": "A vector space is also closed under scalar multiplication.",
                    "description": "a better and longer description",
                },
                {"name": "Basis", "context_snippet": None, "description": None},
            ],
            "edges": [
                {
                    "src_name": "Vector Space",
                    "tgt_name": "Basis",
                    "relation_type": "contains",
                    "description": "short",
                    "keywords": ["span", "span", " closure "],
                    "weight": 1.2,
                },
                {
                    "src_name": "vector space",
                    "tgt_name": "basis",
                    "relation_type": "contains",
                    "description": "longer description for this relation",
                    "keywords": ["closure", "dimension"],
                    "weight": 0.4,
                },
            ],
        }
    )

    extraction = extract_raw_graph_from_chunk(
        llm_client=llm,
        chunk_text="Chunk fallback context text.",
        concept_description_max_chars=500,
        edge_description_max_chars=300,
    )

    assert len(extraction.concepts) == 2
    vector_space = next(
        concept for concept in extraction.concepts if concept.name == "Vector Space"
    )
    assert "scalar multiplication" in vector_space.context_snippet
    assert vector_space.description == "a better and longer description"

    basis = next(concept for concept in extraction.concepts if concept.name == "Basis")
    assert basis.context_snippet == "Chunk fallback context text."

    assert len(extraction.edges) == 1
    edge = extraction.edges[0]
    assert edge.src_name == "Vector Space"
    assert edge.tgt_name == "Basis"
    assert edge.description == "longer description for this relation"
    assert edge.keywords == ["span", "closure", "dimension"]
    assert edge.weight == pytest.approx(1.2)


def test_extract_raw_graph_rejects_invalid_schema() -> None:
    """Extraction should fail fast on malformed LLM output."""
    llm = StubExtractionLLM({"concepts": [{"bad_field": "x"}], "edges": []})

    with pytest.raises(ValueError, match="schema validation failed"):
        extract_raw_graph_from_chunk(
            llm_client=llm,
            chunk_text="chunk",
            concept_description_max_chars=500,
            edge_description_max_chars=300,
        )
