"""Evidence planner: typed retrieval plan for the tutor turn.

AR2.1: Makes evidence selection explicit and inspectable by capturing
retrieval goals, budgets, expansion decisions, and results in a single
typed object reusable from both blocking and streaming paths.

AR2.2: Adds bounded follow-up retrieval loops with subquery expansion
and per-pass budget tracking.
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
    "max_passes_reached",
    "initial",
]

# Minimum average score to consider coverage sufficient
_COVERAGE_SCORE_THRESHOLD = 0.35
# Minimum number of chunks before follow-ups are skipped
_COVERAGE_MIN_CHUNKS = 3


@dataclass(frozen=True)
class EvidencePlan:
    """Immutable, inspectable plan for evidence gathering.

    The plan captures *what* evidence was sought and *why* retrieval
    stopped.  It wraps the current hybrid retrieval as stage 1 and
    supports bounded follow-up loops (AR2.2) and graph/summary
    expansion (AR2.3).
    """

    # ── Query intent ──────────────────────────────────────────────
    base_query: str
    workspace_id: int

    # ── Concept context ───────────────────────────────────────────
    candidate_concept_ids: list[int] = field(default_factory=list)
    graph_root_concept_id: int | None = None
    concept_name: str | None = None

    # ── Expansion flags ──────────────────────────────────────────
    subqueries: list[str] = field(default_factory=list)
    expand_graph_neighbors: bool = False
    graph_hop_budget: int = 0
    provenance_linked_chunk_ids: list[int] = field(default_factory=list)
    expand_document_summaries: bool = False

    # ── Budget ────────────────────────────────────────────────────
    retrieval_budget: int = 20
    max_retrieval_passes: int = 1

    # ── Result / stop ─────────────────────────────────────────────
    stop_reason: StopReason = "initial"
    retrieved_chunk_count: int = 0
    retrieval_passes_used: int = 0
    provenance_chunks_added: int = 0
    expanded_document_ids: list[int] = field(default_factory=list)
    graph_evidence_context: str = ""

    def with_results(
        self,
        *,
        stop_reason: StopReason,
        retrieved_chunk_count: int,
        retrieval_passes_used: int | None = None,
        provenance_chunks_added: int | None = None,
        expanded_document_ids: list[int] | None = None,
    ) -> EvidencePlan:
        """Return a copy capturing post-retrieval results."""
        return EvidencePlan(
            base_query=self.base_query,
            workspace_id=self.workspace_id,
            candidate_concept_ids=self.candidate_concept_ids,
            graph_root_concept_id=self.graph_root_concept_id,
            concept_name=self.concept_name,
            subqueries=self.subqueries,
            expand_graph_neighbors=self.expand_graph_neighbors,
            graph_hop_budget=self.graph_hop_budget,
            provenance_linked_chunk_ids=self.provenance_linked_chunk_ids,
            expand_document_summaries=self.expand_document_summaries,
            retrieval_budget=self.retrieval_budget,
            max_retrieval_passes=self.max_retrieval_passes,
            stop_reason=stop_reason,
            retrieved_chunk_count=retrieved_chunk_count,
            retrieval_passes_used=(
                retrieval_passes_used
                if retrieval_passes_used is not None
                else self.retrieval_passes_used
            ),
            provenance_chunks_added=(
                provenance_chunks_added
                if provenance_chunks_added is not None
                else self.provenance_chunks_added
            ),
            expanded_document_ids=(
                expanded_document_ids
                if expanded_document_ids is not None
                else self.expanded_document_ids
            ),
        )

    @property
    def needs_retrieval(self) -> bool:
        return self.stop_reason != "no_retrieval_needed"

    @property
    def budget_exhausted(self) -> bool:
        return self.retrieved_chunk_count >= self.retrieval_budget


def _plan_follow_up_subqueries(
    *,
    base_query: str,
    concept_name: str | None,
    neighbor_names: list[str] | None = None,
) -> list[str]:
    """Generate follow-up subqueries from concept context.

    Returns a list of alternative queries that could widen evidence
    coverage.  Uses concept name and graph-neighbor names.
    """
    subqueries: list[str] = []
    if (
        concept_name
        and concept_name.lower().strip() not in base_query.lower()
    ):
        subqueries.append(concept_name)
    for name in neighbor_names or []:
        normalized = name.lower().strip()
        if normalized and normalized not in base_query.lower():
            subqueries.append(name)
    return subqueries


_GRAPH_HOP_BUDGET_DEFAULT = 1
_GRAPH_MAX_NEIGHBOR_SUBQUERIES = 2
_PROVENANCE_EXPANSION_BUDGET = 10


def _rollback_session_if_possible(session: object) -> None:
    rollback = getattr(session, "rollback", None)
    if callable(rollback):
        rollback()


def _discover_provenance_chunk_ids(
    session: object,
    *,
    workspace_id: int,
    concept_id: int,
) -> list[int]:
    """Return provenance-linked chunk IDs for a concept.

    Uses the provenance table to find chunks that are linked to the
    concept.  Returns empty list on failure or if session lacks execute
    capability (test stubs).
    """
    if not hasattr(session, "execute"):
        return []
    try:
        from sqlalchemy import text

        rows = (
            session.execute(
                text(
                    """
                    SELECT chunk_id
                    FROM provenance
                    WHERE workspace_id = :workspace_id
                      AND target_type = 'concept'
                      AND target_id = :concept_id
                    ORDER BY chunk_id ASC
                    LIMIT 50
                    """
                ),
                {"workspace_id": workspace_id, "concept_id": concept_id},
            )
            .mappings()
            .all()
        )
        return [int(row["chunk_id"]) for row in rows]
    except Exception:
        _rollback_session_if_possible(session)
        log.debug(
            "provenance discovery failed for concept_id=%d",
            concept_id,
            exc_info=True,
        )
        return []


def _expand_graph_neighbors(
    session: object,  # sqlalchemy.orm.Session
    *,
    workspace_id: int,
    concept_id: int,
    max_hops: int = _GRAPH_HOP_BUDGET_DEFAULT,
) -> tuple[list[str], str]:
    """Return canonical names and a structured context string for graph neighbors.

    Uses get_bounded_subgraph to find neighbors within max_hops, then
    returns (names, context_string).  Names are used as subqueries;
    context_string is a formatted evidence pack for the tutor prompt.
    Returns ([], "") on failure.
    """
    try:
        from domain.graph.explore import get_bounded_subgraph
    except ImportError:
        return [], ""

    if not hasattr(session, "execute"):
        return [], ""

    try:
        subgraph = get_bounded_subgraph(
            session,
            workspace_id=workspace_id,
            concept_id=concept_id,
            max_hops=max_hops,
            max_nodes=10,
            max_edges=20,
        )
    except Exception:
        _rollback_session_if_possible(session)
        log.debug("graph expansion failed for concept_id=%d", concept_id, exc_info=True)
        return [], ""

    names: list[str] = []
    context_parts: list[str] = []

    for node in subgraph.get("nodes", []):
        cid = node.get("concept_id")
        name = node.get("canonical_name", "")
        desc = node.get("description", "")
        if cid == concept_id:
            if desc:
                context_parts.insert(0, f"- {name} (active): {desc}")
            continue
        if name:
            names.append(name)
            if desc:
                context_parts.append(f"- {name}: {desc}")
            else:
                context_parts.append(f"- {name}")

    for edge in subgraph.get("edges", []):
        rel = edge.get("relation_type", "")
        edge_desc = edge.get("description", "")
        if rel and edge_desc:
            context_parts.append(f"  [{rel}] {edge_desc}")

    context = "\n".join(context_parts[:10])  # cap context lines
    return names[:_GRAPH_MAX_NEIGHBOR_SUBQUERIES], context


def build_evidence_plan(
    *,
    base_query: str,
    workspace_id: int,
    needs_retrieval: bool,
    top_k: int = 20,
    concept_id: int | None = None,
    concept_name: str | None = None,
    max_retrieval_passes: int = 2,
    session: object | None = None,
) -> EvidencePlan:
    """Build an evidence plan from turn context.

    When a concept is resolved, the planner discovers graph-adjacent
    concept names (AR2.3) and uses them as follow-up subqueries.
    """
    if not needs_retrieval:
        return EvidencePlan(
            base_query=base_query,
            workspace_id=workspace_id,
            retrieval_budget=0,
            stop_reason="no_retrieval_needed",
        )

    candidate_concept_ids = [concept_id] if concept_id is not None else []

    # ── Graph-neighbor expansion (AR2.3) ──────────────────────────
    neighbor_names: list[str] = []
    graph_context = ""
    expand_graph = False
    graph_hop_budget = 0
    provenance_ids: list[int] = []
    if concept_id is not None and session is not None:
        neighbor_names, graph_context = _expand_graph_neighbors(
            session,
            workspace_id=workspace_id,
            concept_id=concept_id,
        )
        if neighbor_names:
            expand_graph = True
            graph_hop_budget = _GRAPH_HOP_BUDGET_DEFAULT
        # ── Provenance-linked chunk discovery (AR2.5) ─────────────
        provenance_ids = _discover_provenance_chunk_ids(
            session,
            workspace_id=workspace_id,
            concept_id=concept_id,
        )

    subqueries = _plan_follow_up_subqueries(
        base_query=base_query,
        concept_name=concept_name,
        neighbor_names=neighbor_names,
    )

    plan = EvidencePlan(
        base_query=base_query,
        workspace_id=workspace_id,
        candidate_concept_ids=candidate_concept_ids,
        graph_root_concept_id=concept_id,
        concept_name=concept_name,
        subqueries=subqueries,
        expand_graph_neighbors=expand_graph,
        graph_hop_budget=graph_hop_budget,
        provenance_linked_chunk_ids=provenance_ids,
        expand_document_summaries=True,
        graph_evidence_context=graph_context,
        retrieval_budget=top_k,
        max_retrieval_passes=max_retrieval_passes,
    )
    log.info(
        "evidence_plan query=%r budget=%d concept_ids=%s subqueries=%s passes=%d",
        base_query[:80],
        plan.retrieval_budget,
        candidate_concept_ids,
        subqueries,
        plan.max_retrieval_passes,
    )
    return plan


def _coverage_sufficient(chunks: list[RankedChunk]) -> bool:
    """Return True when retrieved chunks already provide adequate coverage."""
    if len(chunks) < _COVERAGE_MIN_CHUNKS:
        return False
    avg_score = sum(c.score for c in chunks) / len(chunks) if chunks else 0.0
    return avg_score >= _COVERAGE_SCORE_THRESHOLD


def _merge_chunks(
    existing: list[RankedChunk],
    new: list[RankedChunk],
    budget: int,
) -> list[RankedChunk]:
    """Merge new chunks into existing, deduplicating by chunk_id and respecting budget."""
    seen = {c.chunk_id for c in existing}
    merged = list(existing)
    for chunk in new:
        if chunk.chunk_id not in seen and len(merged) < budget:
            seen.add(chunk.chunk_id)
            merged.append(chunk)
    return merged


def execute_evidence_plan(
    session: object,  # sqlalchemy.orm.Session
    *,
    plan: EvidencePlan,
    settings: object,  # core.settings.Settings
    on_pass: object | None = None,  # Optional callable(pass_number, query) for status
) -> tuple[EvidencePlan, list[RankedChunk]]:
    """Execute evidence plan with bounded follow-up retrieval loops.

    Pass 1 retrieves using base_query.  Subsequent passes use planned
    subqueries if coverage is insufficient and budget allows.  Results
    are merged and deduplicated across passes.

    The optional ``on_pass`` callback is called before each retrieval
    pass with ``(pass_number: int, query: str)`` for status emission.
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
            retrieval_passes_used=0,
        ), []

    # ── Pass 1: base query ────────────────────────────────────────
    if callable(on_pass):
        on_pass(1, plan.base_query)

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
            retrieval_passes_used=1,
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

    passes_used = 1

    # ── Follow-up passes (AR2.2) ──────────────────────────────────
    for subquery in plan.subqueries:
        if passes_used >= plan.max_retrieval_passes:
            break
        if len(ranked_chunks) >= plan.retrieval_budget:
            break
        if _coverage_sufficient(ranked_chunks):
            break

        passes_used += 1
        if callable(on_pass):
            on_pass(passes_used, subquery)

        follow_up_chunks = retrieve_ranked_chunks(
            session,
            workspace_id=plan.workspace_id,
            query=subquery,
            top_k=plan.retrieval_budget,
            settings=settings,
        )
        ranked_chunks = _merge_chunks(
            ranked_chunks, follow_up_chunks, plan.retrieval_budget
        )

    # ── Provenance-linked expansion (AR2.5) ───────────────────────
    provenance_added = 0
    if (
        plan.provenance_linked_chunk_ids
        and len(ranked_chunks) < plan.retrieval_budget
    ):
        from domain.chat.retrieval_context import retrieve_chunks_by_ids

        existing_ids = {c.chunk_id for c in ranked_chunks}
        missing_ids = [
            cid
            for cid in plan.provenance_linked_chunk_ids
            if cid not in existing_ids
        ][:_PROVENANCE_EXPANSION_BUDGET]

        if missing_ids:
            provenance_chunks = retrieve_chunks_by_ids(
                session,
                workspace_id=plan.workspace_id,
                chunk_ids=missing_ids,
            )
            pre_count = len(ranked_chunks)
            ranked_chunks = _merge_chunks(
                ranked_chunks, provenance_chunks, plan.retrieval_budget
            )
            provenance_added = len(ranked_chunks) - pre_count
            log.info(
                "provenance_expansion added=%d from=%d candidates",
                provenance_added,
                len(missing_ids),
            )

    # ── Document-summary expansion (AR2.5) ────────────────────────
    doc_ids: list[int] = []
    if plan.expand_document_summaries and ranked_chunks:
        doc_ids = list(dict.fromkeys(c.document_id for c in ranked_chunks))[:5]

    # ── Determine stop reason ─────────────────────────────────────
    if len(ranked_chunks) >= plan.retrieval_budget:
        stop: StopReason = "budget_exhausted"
    elif passes_used >= plan.max_retrieval_passes:
        stop = "max_passes_reached"
    else:
        stop = "coverage_sufficient"

    final_plan = plan.with_results(
        stop_reason=stop,
        retrieved_chunk_count=len(ranked_chunks),
        retrieval_passes_used=passes_used,
        provenance_chunks_added=provenance_added,
        expanded_document_ids=doc_ids,
    )
    log.info(
        "evidence_plan_executed chunks=%d passes=%d stop=%s provenance=%d doc_ids=%s",
        final_plan.retrieved_chunk_count,
        final_plan.retrieval_passes_used,
        final_plan.stop_reason,
        final_plan.provenance_chunks_added,
        doc_ids,
    )
    return final_plan, ranked_chunks


__all__ = [
    "EvidencePlan",
    "StopReason",
    "build_evidence_plan",
    "execute_evidence_plan",
]
