"""Evidence planner: typed retrieval plan for the tutor turn.

AR2.1: Makes evidence selection explicit and inspectable by capturing
retrieval goals, budgets, expansion decisions, and results in a single
typed object reusable from both blocking and streaming paths.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from domain.retrieval.types import RankedChunk

log = logging.getLogger("domain.retrieval.evidence_planner")

StopReason = Literal[
    "budget_exhausted",
    "coverage_sufficient",
    "no_retrieval_needed",
    "empty_workspace",
    "initial",
]


@dataclass(frozen=True)
class EvidencePlan:
    """Immutable, inspectable plan for a single evidence-gathering pass.

    The plan captures *what* evidence was sought and *why* retrieval
    stopped.  It wraps the current one-shot retrieval as stage 1 and
    is designed to support bounded follow-up loops (AR2.2) and
    graph/summary expansion (AR2.3) later.
    """

    # ── Query intent ──────────────────────────────────────────────
    base_query: str
    workspace_id: int

    # ── Concept context ───────────────────────────────────────────
    candidate_concept_ids: list[int] = field(default_factory=list)
    graph_root_concept_id: int | None = None

    # ── Expansion flags (AR2.2 / AR2.3 will activate these) ──────
    subqueries: list[str] = field(default_factory=list)
    expand_graph_neighbors: bool = False
    graph_hop_budget: int = 0
    provenance_linked_chunk_ids: list[int] = field(default_factory=list)
    expand_document_summaries: bool = False

    # ── Budget ────────────────────────────────────────────────────
    retrieval_budget: int = 20
    retrieval_passes: int = 1

    # ── Result / stop ─────────────────────────────────────────────
    stop_reason: StopReason = "initial"
    retrieved_chunk_count: int = 0

    def with_results(
        self,
        *,
        stop_reason: StopReason,
        retrieved_chunk_count: int,
    ) -> EvidencePlan:
        """Return a copy capturing post-retrieval results."""
        return EvidencePlan(
            base_query=self.base_query,
            workspace_id=self.workspace_id,
            candidate_concept_ids=self.candidate_concept_ids,
            graph_root_concept_id=self.graph_root_concept_id,
            subqueries=self.subqueries,
            expand_graph_neighbors=self.expand_graph_neighbors,
            graph_hop_budget=self.graph_hop_budget,
            provenance_linked_chunk_ids=self.provenance_linked_chunk_ids,
            expand_document_summaries=self.expand_document_summaries,
            retrieval_budget=self.retrieval_budget,
            retrieval_passes=self.retrieval_passes,
            stop_reason=stop_reason,
            retrieved_chunk_count=retrieved_chunk_count,
        )

    @property
    def needs_retrieval(self) -> bool:
        return self.stop_reason != "no_retrieval_needed"

    @property
    def budget_exhausted(self) -> bool:
        return self.retrieved_chunk_count >= self.retrieval_budget


def build_evidence_plan(
    *,
    base_query: str,
    workspace_id: int,
    needs_retrieval: bool,
    top_k: int = 20,
    concept_id: int | None = None,
) -> EvidencePlan:
    """Build an evidence plan from turn context.

    Currently produces a single-pass plan that wraps the existing
    hybrid retriever.  AR2.2 will extend this with subqueries and
    follow-up loops.
    """
    if not needs_retrieval:
        return EvidencePlan(
            base_query=base_query,
            workspace_id=workspace_id,
            retrieval_budget=0,
            stop_reason="no_retrieval_needed",
        )

    candidate_concept_ids = [concept_id] if concept_id is not None else []

    plan = EvidencePlan(
        base_query=base_query,
        workspace_id=workspace_id,
        candidate_concept_ids=candidate_concept_ids,
        graph_root_concept_id=concept_id,
        retrieval_budget=top_k,
    )
    log.info(
        "evidence_plan query=%r budget=%d concept_ids=%s",
        base_query[:80],
        plan.retrieval_budget,
        candidate_concept_ids,
    )
    return plan


def execute_evidence_plan(
    session: object,  # sqlalchemy.orm.Session
    *,
    plan: EvidencePlan,
    settings: object,  # core.settings.Settings
) -> tuple[EvidencePlan, list[RankedChunk]]:
    """Execute a single-pass evidence plan using the existing hybrid retriever.

    Returns the updated plan (with stop_reason and chunk count) and
    the ranked chunks.  The caller is responsible for converting
    chunks into evidence items and citations.
    """
    from domain.chat.retrieval_context import (
        apply_concept_bias,
        retrieve_ranked_chunks,
        workspace_has_no_chunks,
    )

    if not plan.needs_retrieval:
        return plan.with_results(
            stop_reason="no_retrieval_needed",
            retrieved_chunk_count=0,
        ), []

    ranked_chunks = retrieve_ranked_chunks(
        session,
        workspace_id=plan.workspace_id,
        query=plan.base_query,
        top_k=plan.retrieval_budget,
        settings=settings,
    )

    if not ranked_chunks and workspace_has_no_chunks(session, plan.workspace_id):
        return plan.with_results(
            stop_reason="empty_workspace",
            retrieved_chunk_count=0,
        ), []

    # Apply concept bias when a concept is resolved
    if plan.candidate_concept_ids:
        concept_id = plan.candidate_concept_ids[0]
        ranked_chunks = apply_concept_bias(
            session,
            workspace_id=plan.workspace_id,
            concept_id=concept_id,
            chunks=ranked_chunks,
        )

    stop = (
        "budget_exhausted"
        if len(ranked_chunks) >= plan.retrieval_budget
        else "coverage_sufficient"
    )

    final_plan = plan.with_results(
        stop_reason=stop,
        retrieved_chunk_count=len(ranked_chunks),
    )
    log.info(
        "evidence_plan_executed chunks=%d stop=%s",
        final_plan.retrieved_chunk_count,
        final_plan.stop_reason,
    )
    return final_plan, ranked_chunks


__all__ = [
    "EvidencePlan",
    "StopReason",
    "build_evidence_plan",
    "execute_evidence_plan",
]
