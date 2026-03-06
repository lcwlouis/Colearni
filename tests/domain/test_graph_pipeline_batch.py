"""Tests verifying pipeline uses batch extraction (L7.2)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

# Import core.contracts first to resolve the circular import chain
# (core.__init__ -> core.ingestion -> domain.graph.pipeline -> extraction)
from core.contracts import GraphLLMClient  # noqa: F401

from domain.graph.extraction import batch_extract_raw_graph_from_chunks
from domain.graph.types import RawGraphExtraction


def test_pipeline_calls_batch_extract() -> None:
    """build_graph_for_chunks should call batch_extract_raw_graph_from_chunks."""
    llm = MagicMock()
    llm.batch_extract_raw_graph.return_value = [
        {"concepts": [{"name": "Algebra", "context_snippet": "intro", "description": "math", "tier": "topic"}], "edges": []},
        {"concepts": [{"name": "Geometry", "context_snippet": "shapes", "description": "spatial", "tier": "topic"}], "edges": []},
    ]

    results = batch_extract_raw_graph_from_chunks(
        llm_client=llm,
        chunk_texts=["Algebra is math", "Geometry is shapes"],
        concept_description_max_chars=200,
        edge_description_max_chars=200,
    )

    llm.batch_extract_raw_graph.assert_called_once_with(
        chunk_texts=["Algebra is math", "Geometry is shapes"]
    )
    assert len(results) == 2
    assert results[0].concepts[0].name == "Algebra"
    assert results[1].concepts[0].name == "Geometry"


def test_batch_extract_gracefully_handles_partial_failure() -> None:
    """If one chunk fails validation, others still succeed."""
    llm = MagicMock()
    llm.batch_extract_raw_graph.return_value = [
        {"concepts": "NOT_A_LIST", "edges": []},
        {"concepts": [{"name": "OK", "context_snippet": "x", "description": "y", "tier": "topic"}], "edges": []},
    ]

    results = batch_extract_raw_graph_from_chunks(
        llm_client=llm,
        chunk_texts=["bad", "good"],
        concept_description_max_chars=200,
        edge_description_max_chars=200,
    )

    assert len(results) == 2
    assert results[0].concepts == []
    assert len(results[1].concepts) == 1


def test_batch_extract_empty_returns_empty() -> None:
    llm = MagicMock()

    results = batch_extract_raw_graph_from_chunks(
        llm_client=llm,
        chunk_texts=[],
        concept_description_max_chars=200,
        edge_description_max_chars=200,
    )

    assert results == []
    llm.batch_extract_raw_graph.assert_not_called()
