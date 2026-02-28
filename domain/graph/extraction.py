"""Schema-first LLM raw graph extraction helpers."""

from __future__ import annotations

from core.contracts import GraphLLMClient
from core.observability import observation_context
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from domain.graph.types import (
    ExtractedConcept,
    ExtractedEdge,
    RawGraphExtraction,
    dedupe_keywords,
    normalize_alias,
    truncate_text,
)

_MAX_CONTEXT_SNIPPET_CHARS = 240


class _ConceptPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    context_snippet: str | None = None
    description: str | None = None


class _EdgePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    src_name: str = Field(min_length=1)
    tgt_name: str = Field(min_length=1)
    relation_type: str = Field(min_length=1)
    description: str | None = None
    keywords: list[str] = Field(default_factory=list)
    weight: float = Field(default=1.0, ge=0.0)


class _RawGraphPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concepts: list[_ConceptPayload] = Field(default_factory=list)
    edges: list[_EdgePayload] = Field(default_factory=list)


def extract_raw_graph_from_chunk(
    *,
    llm_client: GraphLLMClient,
    chunk_text: str,
    concept_description_max_chars: int,
    edge_description_max_chars: int,
) -> RawGraphExtraction:
    """Extract and normalize raw concepts/edges for one chunk."""
    try:
        with observation_context(component="graph", operation="graph.extract"):
            payload = _RawGraphPayload.model_validate(
                llm_client.extract_raw_graph(chunk_text=chunk_text)
            )
    except ValidationError as exc:
        raise ValueError(f"Graph extraction schema validation failed: {exc}") from exc

    concept_by_alias: dict[str, ExtractedConcept] = {}
    for concept in payload.concepts:
        alias_norm = normalize_alias(concept.name)
        if not alias_norm:
            continue

        candidate = ExtractedConcept(
            name=concept.name.strip(),
            context_snippet=truncate_text(
                concept.context_snippet or chunk_text,
                _MAX_CONTEXT_SNIPPET_CHARS,
            ),
            description=truncate_text(concept.description, concept_description_max_chars),
        )
        existing = concept_by_alias.get(alias_norm)
        if existing is None:
            concept_by_alias[alias_norm] = candidate
            continue

        merged_description = (
            candidate.description
            if len(candidate.description) > len(existing.description)
            else existing.description
        )
        merged_context = (
            candidate.context_snippet
            if len(candidate.context_snippet) > len(existing.context_snippet)
            else existing.context_snippet
        )
        concept_by_alias[alias_norm] = ExtractedConcept(
            name=existing.name,
            context_snippet=merged_context,
            description=merged_description,
        )

    edge_by_key: dict[tuple[str, str, str], ExtractedEdge] = {}
    for edge in payload.edges:
        src_norm = normalize_alias(edge.src_name)
        tgt_norm = normalize_alias(edge.tgt_name)
        relation_norm = normalize_alias(edge.relation_type)
        if not src_norm or not tgt_norm or not relation_norm:
            continue

        key = (src_norm, tgt_norm, relation_norm)
        candidate = ExtractedEdge(
            src_name=edge.src_name.strip(),
            tgt_name=edge.tgt_name.strip(),
            relation_type=edge.relation_type.strip(),
            description=truncate_text(edge.description, edge_description_max_chars),
            keywords=dedupe_keywords(edge.keywords),
            weight=min(99, max(1, int(edge.weight))),
        )

        existing = edge_by_key.get(key)
        if existing is None:
            edge_by_key[key] = candidate
            continue

        merged_keywords = dedupe_keywords(existing.keywords + candidate.keywords)
        merged_description = (
            candidate.description
            if len(candidate.description) > len(existing.description)
            else existing.description
        )
        edge_by_key[key] = ExtractedEdge(
            src_name=existing.src_name,
            tgt_name=existing.tgt_name,
            relation_type=existing.relation_type,
            description=merged_description,
            keywords=merged_keywords,
            weight=min(99, max(existing.weight, candidate.weight)),
        )

    return RawGraphExtraction(
        concepts=list(concept_by_alias.values()),
        edges=list(edge_by_key.values()),
        extracted_json=payload.model_dump(mode="python"),
    )
