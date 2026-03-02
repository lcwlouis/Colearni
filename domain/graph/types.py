"""Shared graph extraction/resolution domain types."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_alias(value: str) -> str:
    """Normalize an alias for deterministic matching and map lookups."""
    return _WHITESPACE_PATTERN.sub(" ", value.strip().casefold())


def truncate_text(value: str | None, max_chars: int) -> str:
    """Return a bounded string for storage fields with max-char rules."""
    if not value:
        return ""
    bounded = value.strip()
    if len(bounded) <= max_chars:
        return bounded
    return bounded[: max_chars - 1].rstrip() + "…"


def dedupe_keywords(keywords: list[str]) -> list[str]:
    """De-duplicate edge keywords while preserving stable first-seen order."""
    deduped: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        normalized = normalize_alias(keyword)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(keyword.strip())
    return deduped


VALID_TIERS: frozenset[str] = frozenset({"umbrella", "topic", "subtopic", "granular"})

DEFAULT_TIER: str = "granular"

_TIER_RANK: dict[str, int] = {"umbrella": 1, "topic": 2, "subtopic": 3, "granular": 4}


def tier_rank(tier: str | None) -> int:
    """Return specificity rank for a tier value (higher = more specific, 0 = unknown/None)."""
    return _TIER_RANK.get(tier or "", 0)


def build_tier_inference_prompt(
    concept_name: str,
    description: str,
    neighbor_names: list[str],
) -> str:
    """Build a short prompt asking the LLM to classify a concept into a tier."""
    neighbors_text = ", ".join(neighbor_names[:10]) if neighbor_names else "(none)"
    return (
        "Classify the following concept into exactly one tier: "
        "umbrella, topic, subtopic, or granular.\n\n"
        f"Concept: {concept_name}\n"
        f"Description: {description or '(no description)'}\n"
        f"Neighbor concepts: {neighbors_text}\n\n"
        "Respond with a single word: umbrella, topic, subtopic, or granular."
    )


@dataclass(frozen=True, slots=True)
class ExtractedConcept:
    """One raw concept extracted from a chunk."""

    name: str
    context_snippet: str
    description: str = ""
    tier: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractedEdge:
    """One raw edge extracted from a chunk."""

    src_name: str
    tgt_name: str
    relation_type: str
    description: str = ""
    keywords: list[str] = field(default_factory=list)
    weight: int = 1


@dataclass(frozen=True, slots=True)
class RawGraphExtraction:
    """Normalized extraction output for one chunk."""

    concepts: list[ExtractedConcept]
    edges: list[ExtractedEdge]
    extracted_json: dict[str, object]


@dataclass(frozen=True, slots=True)
class CanonicalCandidate:
    """Bounded canonical candidate for online disambiguation."""

    concept_id: int
    canonical_name: str
    description: str
    aliases: tuple[str, ...]
    lexical_similarity: float | None = None
    vector_similarity: float | None = None


@dataclass(frozen=True, slots=True)
class ResolverDecision:
    """Final merge/create decision for one raw concept."""

    decision: Literal["MERGE_INTO", "CREATE_NEW"]
    merge_into_id: int | None
    confidence: float
    method: Literal["exact", "lexical", "vector", "llm", "fallback"]
    alias_to_add: str | None = None
    proposed_description: str | None = None
    llm_used: bool = False


@dataclass(slots=True)
class ResolverBudgets:
    """Runtime LLM budget tracker for one document/chunk pass."""

    max_llm_calls_per_chunk: int
    max_llm_calls_per_document: int
    llm_calls_chunk: int = 0
    llm_calls_document: int = 0
    last_hard_stop_reason: str | None = None

    def reset_chunk(self) -> None:
        """Reset chunk-local counters while preserving document counter."""
        self.llm_calls_chunk = 0
        self.last_hard_stop_reason = None

    def can_call_llm(self) -> bool:
        """Return whether another LLM call is allowed under hard limits."""
        if self.llm_calls_chunk >= self.max_llm_calls_per_chunk:
            self.last_hard_stop_reason = "chunk_cap_reached"
            return False
        if self.llm_calls_document >= self.max_llm_calls_per_document:
            self.last_hard_stop_reason = "document_cap_reached"
            return False
        self.last_hard_stop_reason = None
        return True

    def register_llm_call(self) -> None:
        """Record one LLM call and enforce hard-stop caps."""
        if not self.can_call_llm():
            raise RuntimeError("LLM budget exhausted")
        self.llm_calls_chunk += 1
        self.llm_calls_document += 1


@dataclass(frozen=True, slots=True)
class ResolvedConcept:
    """Canonical resolution result for one concept mention."""

    concept_id: int
    created: bool
    method: str
    used_llm: bool


@dataclass(frozen=True, slots=True)
class GraphBuildResult:
    """Counters from one graph build pass."""

    raw_concepts_written: int
    raw_edges_written: int
    canonical_created: int
    canonical_merged: int
    canonical_edges_upserted: int
    llm_disambiguations: int
