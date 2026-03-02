"""Offline graph gardener: bounded cluster merges for canonical concepts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from adapters.db import graph_repository
from adapters.db.graph.provenance import count_provenance_for_concepts
from adapters.db.mastery import get_mastered_concept_ids
from core.contracts import GraphLLMClient
from domain.graph.orphan_pruner import prune_orphan_graph_nodes
from core.observability import (
    SPAN_KIND_CHAIN,
    emit_event,
    observation_context,
    set_span_summary,
    start_span,
)
from core.settings import Settings
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from domain.graph.types import CanonicalCandidate, DEFAULT_TIER, VALID_TIERS, build_tier_inference_prompt, normalize_alias, tier_rank

_GARDENER_REASON = "gardener_cluster_merge"


@dataclass(frozen=True, slots=True)
class GardenerConfig:
    """Runtime knobs for one bounded gardener invocation."""

    lexical_top_k: int
    vector_top_k: int
    candidate_cap: int
    cluster_llm_confidence_floor: float
    max_llm_calls_per_run: int
    max_clusters_per_run: int
    max_dirty_nodes_per_run: int
    recent_window_days: int
    edge_weight_cap: float
    edge_description_max_chars: int

    @classmethod
    def from_settings(cls, settings: Settings) -> GardenerConfig:
        return cls(
            lexical_top_k=settings.resolver_lexical_top_k,
            vector_top_k=settings.resolver_vector_top_k,
            candidate_cap=settings.resolver_candidate_cap,
            cluster_llm_confidence_floor=0.70,
            max_llm_calls_per_run=settings.gardener_max_llm_calls_per_run,
            max_clusters_per_run=settings.gardener_max_clusters_per_run,
            max_dirty_nodes_per_run=settings.gardener_max_dirty_nodes_per_run,
            recent_window_days=settings.gardener_recent_window_days,
            edge_weight_cap=settings.resolver_edge_weight_cap,
            edge_description_max_chars=settings.resolver_edge_description_max_chars,
        )


@dataclass(slots=True)
class GardenerBudgets:
    """Hard-stop budget counters for a gardener run."""

    max_llm_calls_per_run: int
    max_clusters_per_run: int
    llm_calls: int = 0
    clusters_processed: int = 0

    def can_process_cluster(self) -> bool:
        return self.clusters_processed < self.max_clusters_per_run

    def can_call_llm(self) -> bool:
        return self.llm_calls < self.max_llm_calls_per_run

    def register_cluster(self) -> None:
        if not self.can_process_cluster():
            raise RuntimeError("Gardener cluster budget exhausted")
        self.clusters_processed += 1

    def register_llm_call(self) -> None:
        if not self.can_call_llm():
            raise RuntimeError("Gardener LLM budget exhausted")
        self.llm_calls += 1


@dataclass(frozen=True, slots=True)
class GardenerRunResult:
    """Summary of one bounded gardener invocation."""

    seed_nodes_selected: int
    clusters_total: int
    clusters_processed: int
    clusters_skipped: int
    merges_applied: int
    llm_calls: int
    stopped_by_cluster_budget: bool
    stopped_by_llm_budget: bool
    pruned_concepts: int = 0
    pruned_edges: int = 0
    tiers_backfilled: int = 0


@dataclass(frozen=True, slots=True)
class _ClusterConcept:
    concept_id: int
    canonical_name: str
    description: str
    aliases: tuple[str, ...]
    tier: str | None = None
    has_mastery: bool = False
    provenance_count: int = 0
    neighbor_names: tuple[str, ...] = ()


class _GardenerDecisionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: Literal["MERGE_INTO", "CREATE_NEW"]
    merge_into_id: int | None = None
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_merge_id(self) -> _GardenerDecisionPayload:
        if self.decision == "MERGE_INTO" and self.merge_into_id is None:
            raise ValueError("merge_into_id is required when decision=MERGE_INTO")
        return self


def run_graph_gardener(
    session: Session,
    *,
    workspace_id: int,
    llm_client: GraphLLMClient,
    settings: Settings,
    max_dirty_nodes: int | None = None,
    max_clusters: int | None = None,
    max_llm_calls: int | None = None,
    run_id: str | None = None,
) -> GardenerRunResult:
    """Run one bounded offline graph-consolidation pass for one workspace."""
    resolved_run_id = run_id or str(uuid4())
    with observation_context(
        component="graph",
        operation="graph.gardener.run",
        workspace_id=workspace_id,
        run_id=resolved_run_id,
    ), start_span(
        "graph.gardener.run",
        kind=SPAN_KIND_CHAIN,
        component="graph",
        operation="graph.gardener.run",
        workspace_id=workspace_id,
        run_id=resolved_run_id,
    ) as span:
        config = GardenerConfig.from_settings(settings)
        effective_max_dirty_nodes = config.max_dirty_nodes_per_run
        if max_dirty_nodes is not None:
            effective_max_dirty_nodes = min(max_dirty_nodes, config.max_dirty_nodes_per_run)
        if effective_max_dirty_nodes < 1:
            raise ValueError("max_dirty_nodes must be >= 1")

        effective_max_clusters = config.max_clusters_per_run
        if max_clusters is not None:
            effective_max_clusters = min(max_clusters, config.max_clusters_per_run)
        if effective_max_clusters < 0:
            raise ValueError("max_clusters must be >= 0")

        effective_max_llm_calls = config.max_llm_calls_per_run
        if max_llm_calls is not None:
            effective_max_llm_calls = min(max_llm_calls, config.max_llm_calls_per_run)
        if effective_max_llm_calls < 0:
            raise ValueError("max_llm_calls must be >= 0")

        budgets = GardenerBudgets(
            max_llm_calls_per_run=effective_max_llm_calls,
            max_clusters_per_run=effective_max_clusters,
        )
        emit_event(
            "graph.gardener.budget.usage",
            status="info",
            component="graph",
            operation="graph.gardener.run",
            workspace_id=workspace_id,
            llm_calls=budgets.llm_calls,
            clusters_processed=budgets.clusters_processed,
            max_llm_calls_per_run=budgets.max_llm_calls_per_run,
            max_clusters_per_run=budgets.max_clusters_per_run,
        )
        # --- Tier backfill pass: fix NULL-tier concepts before clustering ---
        tiers_backfilled = _backfill_null_tiers(
            session=session,
            workspace_id=workspace_id,
            llm_client=llm_client,
            budgets=budgets,
            limit=effective_max_dirty_nodes,
        )
        seeds = graph_repository.list_gardener_seed_concepts(
            session,
            workspace_id=workspace_id,
            recent_window_days=config.recent_window_days,
            limit=effective_max_dirty_nodes,
        )
        if not seeds:
            return GardenerRunResult(
                seed_nodes_selected=0,
                clusters_total=0,
                clusters_processed=0,
                clusters_skipped=0,
                merges_applied=0,
                llm_calls=budgets.llm_calls,
                stopped_by_cluster_budget=False,
                stopped_by_llm_budget=False,
                tiers_backfilled=tiers_backfilled,
            )

        seed_ids = {seed.id for seed in seeds}
        cluster_concepts: dict[int, _ClusterConcept] = {
            seed.id: _to_cluster_concept(seed) for seed in seeds
        }
        adjacency: dict[int, set[int]] = {seed.id: set() for seed in seeds}

        for seed in seeds:
            candidates = _candidate_blocking(
                session=session,
                workspace_id=workspace_id,
                seed=seed,
                config=config,
            )
            for candidate in candidates:
                cluster_concepts.setdefault(
                    candidate.concept_id,
                    _ClusterConcept(
                        concept_id=candidate.concept_id,
                        canonical_name=candidate.canonical_name,
                        description=candidate.description,
                        aliases=tuple(candidate.aliases),
                    ),
                )
                if candidate.concept_id == seed.id:
                    continue
                adjacency.setdefault(seed.id, set()).add(candidate.concept_id)
                adjacency.setdefault(candidate.concept_id, set()).add(seed.id)

        clusters = _connected_components(adjacency)

        # Enrich cluster concepts with provenance, mastery, and neighbor info
        all_concept_ids = list(cluster_concepts.keys())
        provenance_counts = count_provenance_for_concepts(
            session, workspace_id=workspace_id, concept_ids=all_concept_ids,
        )
        mastered_ids = get_mastered_concept_ids(
            session, workspace_id=workspace_id, concept_ids=all_concept_ids,
        )
        for cid, cc in list(cluster_concepts.items()):
            neighbors = graph_repository.list_neighbor_names(
                session, workspace_id=workspace_id, concept_id=cid,
            )
            cluster_concepts[cid] = _ClusterConcept(
                concept_id=cc.concept_id,
                canonical_name=cc.canonical_name,
                description=cc.description,
                aliases=cc.aliases,
                tier=cc.tier,
                has_mastery=cid in mastered_ids,
                provenance_count=provenance_counts.get(cid, 0),
                neighbor_names=tuple(neighbors),
            )

        stabilized_seed_ids: set[int] = set()
        merges_applied = 0
        clusters_skipped = 0
        stopped_by_cluster_budget = False
        stopped_by_llm_budget = False

        for cluster in clusters:
            cluster_seed_ids = seed_ids.intersection(cluster)
            if not cluster_seed_ids:
                continue
            if len(cluster) < 2:
                stabilized_seed_ids.update(cluster_seed_ids)
                continue

            if not budgets.can_process_cluster():
                stopped_by_cluster_budget = True
                emit_event(
                    "graph.gardener.budget.hard_stop",
                    status="warning",
                    component="graph",
                    operation="graph.gardener.run",
                    workspace_id=workspace_id,
                    reason="cluster_budget_exhausted",
                    llm_calls=budgets.llm_calls,
                    clusters_processed=budgets.clusters_processed,
                    max_llm_calls_per_run=budgets.max_llm_calls_per_run,
                    max_clusters_per_run=budgets.max_clusters_per_run,
                )
                break
            if not budgets.can_call_llm():
                stopped_by_llm_budget = True
                emit_event(
                    "graph.gardener.budget.hard_stop",
                    status="warning",
                    component="graph",
                    operation="graph.gardener.run",
                    workspace_id=workspace_id,
                    reason="llm_budget_exhausted",
                    llm_calls=budgets.llm_calls,
                    clusters_processed=budgets.clusters_processed,
                    max_llm_calls_per_run=budgets.max_llm_calls_per_run,
                    max_clusters_per_run=budgets.max_clusters_per_run,
                )
                break
            budgets.register_cluster()
            budgets.register_llm_call()
            emit_event(
                "graph.gardener.budget.usage",
                status="info",
                component="graph",
                operation="graph.gardener.run",
                workspace_id=workspace_id,
                llm_calls=budgets.llm_calls,
                clusters_processed=budgets.clusters_processed,
                max_llm_calls_per_run=budgets.max_llm_calls_per_run,
                max_clusters_per_run=budgets.max_clusters_per_run,
            )

            decision = _cluster_llm_decision(
                llm_client=llm_client,
                concepts=cluster_concepts,
                cluster=cluster,
            )
            if decision is None:
                clusters_skipped += 1
                emit_event(
                    "graph.gardener.cluster.skip",
                    status="info",
                    component="graph",
                    operation="graph.gardener.run",
                    workspace_id=workspace_id,
                    cluster_size=len(cluster),
                    reason="llm_returned_none",
                )
                continue
            if decision.confidence < config.cluster_llm_confidence_floor:
                clusters_skipped += 1
                emit_event(
                    "graph.gardener.cluster.skip",
                    status="info",
                    component="graph",
                    operation="graph.gardener.run",
                    workspace_id=workspace_id,
                    cluster_size=len(cluster),
                    reason="low_confidence",
                    confidence=decision.confidence,
                    threshold=config.cluster_llm_confidence_floor,
                )
                continue
            target_id = decision.merge_into_id
            if target_id is None or target_id not in cluster:
                clusters_skipped += 1
                emit_event(
                    "graph.gardener.cluster.skip",
                    status="info",
                    component="graph",
                    operation="graph.gardener.run",
                    workspace_id=workspace_id,
                    cluster_size=len(cluster),
                    reason="invalid_target",
                )
                continue

            merge_away_ids = sorted(cluster_seed_ids - {target_id})
            for source_id in merge_away_ids:
                # Mastery protection: never merge away a concept with learning progress
                if cluster_concepts[source_id].has_mastery:
                    emit_event(
                        "graph.gardener.merge.skip",
                        status="info",
                        component="graph",
                        operation="graph.gardener.run",
                        workspace_id=workspace_id,
                        source_id=source_id,
                        reason="mastery_protection",
                    )
                    continue
                if _execute_merge(
                    session=session,
                    workspace_id=workspace_id,
                    from_concept_id=source_id,
                    to_concept_id=target_id,
                    confidence=decision.confidence,
                    method="llm",
                    reason=_GARDENER_REASON,
                    edge_weight_cap=config.edge_weight_cap,
                    edge_description_max_chars=config.edge_description_max_chars,
                ):
                    merges_applied += 1

            if target_id in seed_ids:
                stabilized_seed_ids.add(target_id)

        for concept_id in sorted(stabilized_seed_ids):
            graph_repository.set_canonical_concept_dirty(
                session,
                workspace_id=workspace_id,
                concept_id=concept_id,
                dirty=False,
            )

        emit_event(
            "graph.gardener.budget.usage",
            status="info",
            component="graph",
            operation="graph.gardener.run",
            workspace_id=workspace_id,
            llm_calls=budgets.llm_calls,
            clusters_processed=budgets.clusters_processed,
            max_llm_calls_per_run=budgets.max_llm_calls_per_run,
            max_clusters_per_run=budgets.max_clusters_per_run,
        )
        prune_result = prune_orphan_graph_nodes(session, workspace_id=workspace_id)
        result = GardenerRunResult(
            seed_nodes_selected=len(seeds),
            clusters_total=len(clusters),
            clusters_processed=budgets.clusters_processed,
            clusters_skipped=clusters_skipped,
            merges_applied=merges_applied,
            llm_calls=budgets.llm_calls,
            stopped_by_cluster_budget=stopped_by_cluster_budget,
            stopped_by_llm_budget=stopped_by_llm_budget,
            pruned_concepts=prune_result["pruned_concepts"],
            pruned_edges=prune_result["pruned_edges"],
            tiers_backfilled=tiers_backfilled,
        )
        if span is not None:
            span.set_attribute("graph.seed_nodes", len(seeds))
            span.set_attribute("graph.clusters_total", len(clusters))
            span.set_attribute("graph.clusters_processed", budgets.clusters_processed)
            span.set_attribute("graph.clusters_skipped", clusters_skipped)
            span.set_attribute("graph.merges_applied", merges_applied)
            span.set_attribute("graph.llm_calls", budgets.llm_calls)
            span.set_attribute("graph.stopped_by_cluster_budget", stopped_by_cluster_budget)
            span.set_attribute("graph.stopped_by_llm_budget", stopped_by_llm_budget)
            set_span_summary(
                span,
                input_summary=f"workspace={workspace_id}, seeds={len(seeds)}",
                output_summary=(
                    f"processed={budgets.clusters_processed}, merges={merges_applied}, "
                    f"llm={budgets.llm_calls}"
                    + (", budget_stop" if stopped_by_cluster_budget or stopped_by_llm_budget else "")
                ),
            )
        return result


def _backfill_null_tiers(
    *,
    session: Session,
    workspace_id: int,
    llm_client: GraphLLMClient,
    budgets: GardenerBudgets,
    limit: int,
) -> int:
    """Infer and set tier for concepts with tier IS NULL. Returns count of backfilled concepts."""
    null_tier_concepts = graph_repository.list_null_tier_concepts(
        session, workspace_id=workspace_id, limit=limit,
    )
    backfilled = 0
    for concept in null_tier_concepts:
        if not budgets.can_call_llm():
            break
        budgets.register_llm_call()
        neighbor_names = graph_repository.list_neighbor_names(
            session, workspace_id=workspace_id, concept_id=concept.id,
        )
        prompt_sys, prompt_user = build_tier_inference_prompt(
            concept_name=concept.canonical_name,
            description=concept.description,
            neighbor_names=neighbor_names,
        )
        try:
            raw = llm_client.generate_tutor_text(
                prompt=prompt_user, system_prompt=prompt_sys,
            ).strip().lower()
            tier = raw if raw in VALID_TIERS else DEFAULT_TIER
        except Exception:
            tier = DEFAULT_TIER
        session.execute(
            text(
                "UPDATE concepts_canon SET tier = :tier"
                " WHERE workspace_id = :workspace_id AND id = :concept_id"
            ),
            {"tier": tier, "workspace_id": workspace_id, "concept_id": concept.id},
        )
        backfilled += 1
        emit_event(
            "graph.gardener.tier_backfill",
            status="info",
            component="graph",
            operation="graph.gardener.run",
            workspace_id=workspace_id,
            concept_id=concept.id,
            inferred_tier=tier,
        )
    return backfilled


def _candidate_blocking(
    *,
    session: Session,
    workspace_id: int,
    seed: graph_repository.CanonicalConceptRow,
    config: GardenerConfig,
) -> list[CanonicalCandidate]:
    lexical = graph_repository.list_lexical_candidates(
        session,
        workspace_id=workspace_id,
        alias=normalize_alias(seed.canonical_name),
        top_k=config.lexical_top_k,
    )
    vectors: list[graph_repository.CanonicalCandidateRow] = []
    if seed.embedding is not None:
        vectors = graph_repository.list_vector_candidates(
            session,
            workspace_id=workspace_id,
            query_embedding=seed.embedding,
            top_k=config.vector_top_k,
        )

    by_id: dict[int, CanonicalCandidate] = {}
    for row in lexical:
        by_id[row.id] = CanonicalCandidate(
            concept_id=row.id,
            canonical_name=row.canonical_name,
            description=row.description,
            aliases=tuple(row.aliases),
            lexical_similarity=row.lexical_similarity,
            vector_similarity=None,
        )
    for row in vectors:
        existing = by_id.get(row.id)
        if existing is None:
            by_id[row.id] = CanonicalCandidate(
                concept_id=row.id,
                canonical_name=row.canonical_name,
                description=row.description,
                aliases=tuple(row.aliases),
                lexical_similarity=None,
                vector_similarity=row.vector_similarity,
            )
            continue
        by_id[row.id] = CanonicalCandidate(
            concept_id=row.id,
            canonical_name=existing.canonical_name,
            description=existing.description,
            aliases=existing.aliases,
            lexical_similarity=existing.lexical_similarity,
            vector_similarity=row.vector_similarity,
        )

    ranked = sorted(
        by_id.values(),
        key=lambda candidate: (
            max(candidate.lexical_similarity or 0.0, candidate.vector_similarity or 0.0),
            candidate.lexical_similarity or -1.0,
            candidate.vector_similarity or -1.0,
            -candidate.concept_id,
        ),
        reverse=True,
    )
    return ranked[: config.candidate_cap]


def _connected_components(adjacency: Mapping[int, set[int]]) -> list[set[int]]:
    components: list[set[int]] = []
    visited: set[int] = set()
    for root in sorted(adjacency):
        if root in visited:
            continue
        stack = [root]
        component: set[int] = set()
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            component.add(node)
            for neighbor in sorted(adjacency.get(node, set()), reverse=True):
                if neighbor not in visited:
                    stack.append(neighbor)
        components.append(component)
    components.sort(key=lambda item: (len(item), min(item)))
    return components


def _cluster_llm_decision(
    *,
    llm_client: GraphLLMClient,
    concepts: Mapping[int, _ClusterConcept],
    cluster: set[int],
) -> _GardenerDecisionPayload | None:
    ordered_ids = sorted(cluster)
    reference = concepts[ordered_ids[0]]
    try:
        with observation_context(operation="graph.disambiguate"):
            payload = llm_client.disambiguate(
                raw_name=reference.canonical_name,
                context_snippet=reference.description,
                candidates=[
                    {
                        "id": concept_id,
                        "canonical_name": concepts[concept_id].canonical_name,
                        "description": concepts[concept_id].description,
                        "aliases": list(concepts[concept_id].aliases),
                        "tier": concepts[concept_id].tier or "unknown",
                        "has_mastery": concepts[concept_id].has_mastery,
                        "provenance_count": concepts[concept_id].provenance_count,
                        "neighbors": list(concepts[concept_id].neighbor_names),
                    }
                    for concept_id in ordered_ids
                ],
            )
        return _GardenerDecisionPayload.model_validate(payload)
    except (ValidationError, RuntimeError, ValueError):
        return None


def _execute_merge(
    *,
    session: Session,
    workspace_id: int,
    from_concept_id: int,
    to_concept_id: int,
    confidence: float,
    method: str,
    reason: str,
    edge_weight_cap: float,
    edge_description_max_chars: int,
) -> bool:
    if from_concept_id == to_concept_id:
        return False
    source = graph_repository.get_canonical_concept(
        session,
        workspace_id=workspace_id,
        concept_id=from_concept_id,
    )
    target = graph_repository.get_canonical_concept(
        session,
        workspace_id=workspace_id,
        concept_id=to_concept_id,
    )
    if source is None or target is None or not source.is_active or not target.is_active:
        return False

    logged = graph_repository.insert_concept_merge_log_idempotent(
        session,
        workspace_id=workspace_id,
        from_id=from_concept_id,
        to_id=to_concept_id,
        reason=reason,
        method=method,
        confidence=confidence,
    )
    graph_repository.repoint_edges_for_merge(
        session,
        workspace_id=workspace_id,
        from_id=from_concept_id,
        to_id=to_concept_id,
        weight_cap=edge_weight_cap,
        edge_description_max_chars=edge_description_max_chars,
    )
    graph_repository.repoint_alias_map(
        session,
        workspace_id=workspace_id,
        from_id=from_concept_id,
        to_id=to_concept_id,
    )
    graph_repository.ensure_aliases_map_to_concept(
        session,
        workspace_id=workspace_id,
        aliases=source.aliases,
        canon_concept_id=to_concept_id,
        confidence=confidence,
        method=method,
    )
    # Preserve the more general tier on the target concept after merge.
    src_rank = tier_rank(source.tier)
    tgt_rank = tier_rank(target.tier)
    if src_rank > 0 and (tgt_rank == 0 or src_rank < tgt_rank):
        session.execute(
            text(
                "UPDATE concepts_canon SET tier = :tier"
                " WHERE workspace_id = :workspace_id AND id = :concept_id"
            ),
            {"tier": source.tier, "workspace_id": workspace_id, "concept_id": to_concept_id},
        )
    deactivated = graph_repository.deactivate_canonical_concept(
        session,
        workspace_id=workspace_id,
        concept_id=from_concept_id,
    )
    graph_repository.set_canonical_concept_dirty(
        session,
        workspace_id=workspace_id,
        concept_id=to_concept_id,
        dirty=False,
    )
    return logged or deactivated


def _to_cluster_concept(concept: graph_repository.CanonicalConceptRow) -> _ClusterConcept:
    return _ClusterConcept(
        concept_id=concept.id,
        canonical_name=concept.canonical_name,
        description=concept.description,
        aliases=tuple(concept.aliases),
        tier=concept.tier,
    )


__all__ = ["GardenerRunResult", "run_graph_gardener"]
