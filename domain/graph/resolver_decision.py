"""Deterministic and LLM-based resolution decisions."""

from __future__ import annotations

from collections.abc import Sequence

from core.observability import emit_event
from domain.graph.types import (
    CanonicalCandidate,
    ResolverBudgets,
    ResolverDecision,
)


def deterministic_lexical_decision(
    candidates: Sequence[CanonicalCandidate],
    *,
    lexical_similarity_threshold: float,
    lexical_margin_threshold: float,
) -> ResolverDecision | None:
    """Return MERGE_INTO if the lexical top-1 is confidently dominant."""
    lexical_ranked = sorted(
        [c for c in candidates if c.lexical_similarity is not None],
        key=lambda c: c.lexical_similarity or -1.0,
        reverse=True,
    )
    if not lexical_ranked:
        return None

    best = float(lexical_ranked[0].lexical_similarity or 0.0)
    second = float(lexical_ranked[1].lexical_similarity or 0.0) if len(lexical_ranked) > 1 else 0.0
    margin = best - second
    if best >= lexical_similarity_threshold and margin >= lexical_margin_threshold:
        return ResolverDecision(
            decision="MERGE_INTO",
            merge_into_id=lexical_ranked[0].concept_id,
            confidence=min(1.0, best),
            method="lexical",
        )
    return None


def deterministic_vector_decision(
    candidates: Sequence[CanonicalCandidate],
    *,
    vector_similarity_threshold: float,
    vector_margin_threshold: float,
) -> ResolverDecision | None:
    """Return MERGE_INTO if the vector top-1 is confidently dominant."""
    vector_ranked = sorted(
        [c for c in candidates if c.vector_similarity is not None],
        key=lambda c: c.vector_similarity or -1.0,
        reverse=True,
    )
    if not vector_ranked:
        return None

    best = float(vector_ranked[0].vector_similarity or 0.0)
    second = float(vector_ranked[1].vector_similarity or 0.0) if len(vector_ranked) > 1 else 0.0
    margin = best - second
    if best >= vector_similarity_threshold and margin >= vector_margin_threshold:
        return ResolverDecision(
            decision="MERGE_INTO",
            merge_into_id=vector_ranked[0].concept_id,
            confidence=min(1.0, best),
            method="vector",
        )
    return None


def emit_resolver_budget_usage(
    *,
    workspace_id: int,
    chunk_id: int,
    budgets: ResolverBudgets,
) -> None:
    """Emit an observability event for current resolver budget usage."""
    emit_event(
        "graph.resolver.budget.usage",
        status="info",
        component="graph",
        operation="graph.resolver.resolve_concept",
        workspace_id=workspace_id,
        chunk_id=chunk_id,
        llm_calls_chunk=budgets.llm_calls_chunk,
        llm_calls_document=budgets.llm_calls_document,
        max_llm_calls_per_chunk=budgets.max_llm_calls_per_chunk,
        max_llm_calls_per_document=budgets.max_llm_calls_per_document,
    )
