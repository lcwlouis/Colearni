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
    disambiguate_batch_size: int
    full_scan_max_seeds: int = 10000
    full_scan_max_clusters: int = 500
    full_scan_max_llm_calls: int = 200
    full_scan_lexical_top_k: int = 20
    full_scan_vector_top_k: int = 30
    full_scan_candidate_cap: int = 30

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
            disambiguate_batch_size=settings.resolver_disambiguate_batch_size,
            full_scan_max_seeds=settings.gardener_full_scan_max_seeds,
            full_scan_max_clusters=settings.gardener_full_scan_max_clusters,
            full_scan_max_llm_calls=settings.gardener_full_scan_max_llm_calls,
            full_scan_lexical_top_k=settings.gardener_full_scan_lexical_top_k,
            full_scan_vector_top_k=settings.gardener_full_scan_vector_top_k,
            full_scan_candidate_cap=settings.gardener_full_scan_candidate_cap,
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
    links_created: int
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
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    decision: Literal["MERGE_INTO", "CREATE_NEW", "LINK_ONLY"]
    merge_into_id: int | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    link_to_id: int | None = None
    link_relation_type: str | None = None

    @model_validator(mode="after")
    def validate_ids(self) -> _GardenerDecisionPayload:
        if self.decision == "MERGE_INTO" and self.merge_into_id is None:
            raise ValueError("merge_into_id is required when decision=MERGE_INTO")
        if self.decision == "LINK_ONLY" and self.link_to_id is None:
            raise ValueError("link_to_id is required when decision=LINK_ONLY")
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
    full_scan: bool = False,
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
        if full_scan and max_dirty_nodes is None:
            effective_max_dirty_nodes = config.full_scan_max_seeds
        elif max_dirty_nodes is not None:
            effective_max_dirty_nodes = min(max_dirty_nodes, config.max_dirty_nodes_per_run)
        if effective_max_dirty_nodes < 1:
            raise ValueError("max_dirty_nodes must be >= 1")

        effective_max_clusters = config.max_clusters_per_run
        if full_scan and max_clusters is None:
            effective_max_clusters = config.full_scan_max_clusters
        elif max_clusters is not None:
            effective_max_clusters = min(max_clusters, config.max_clusters_per_run)
        if effective_max_clusters < 0:
            raise ValueError("max_clusters must be >= 0")

        effective_max_llm_calls = config.max_llm_calls_per_run
        if full_scan and max_llm_calls is None:
            effective_max_llm_calls = config.full_scan_max_llm_calls
        elif max_llm_calls is not None:
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
            full_scan=full_scan,
        )
        if not seeds:
            return GardenerRunResult(
                seed_nodes_selected=0,
                clusters_total=0,
                clusters_processed=0,
                clusters_skipped=0,
                merges_applied=0,
                links_created=0,
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
                full_scan=full_scan,
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
        links_created = 0
        clusters_skipped = 0
        stopped_by_cluster_budget = False
        stopped_by_llm_budget = False

        # Collect clusters eligible for LLM decisions
        pending_clusters: list[tuple[set[int], set[int]]] = []  # (cluster, cluster_seed_ids)
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
            pending_clusters.append((cluster, cluster_seed_ids))

        # Batch LLM disambiguation calls
        batch_size = config.disambiguate_batch_size
        for batch_start in range(0, len(pending_clusters), batch_size):
            batch = pending_clusters[batch_start:batch_start + batch_size]
            cluster_decisions = _batch_cluster_llm_decisions(
                llm_client=llm_client,
                concepts=cluster_concepts,
                clusters=[c for c, _ in batch],
            )
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

            for (cluster, cluster_seed_ids), member_decisions in zip(batch, cluster_decisions):
                if not member_decisions:
                    clusters_skipped += 1
                    continue

                already_merged: set[int] = set()

                for concept_id, decision in member_decisions:
                    if concept_id in already_merged:
                        continue
                    if decision is None:
                        continue
                    if decision.confidence < config.cluster_llm_confidence_floor:
                        continue

                    if decision.decision == "LINK_ONLY" and decision.link_to_id is not None:
                        link_target = decision.link_to_id
                        if link_target in cluster and concept_id != link_target and link_target not in already_merged:
                            relation = decision.link_relation_type or "related_to"
                            graph_repository.upsert_canonical_edge(
                                session,
                                workspace_id=workspace_id,
                                src_id=concept_id,
                                tgt_id=link_target,
                                relation_type=relation,
                                description=(
                                    f"{cluster_concepts[concept_id].canonical_name} "
                                    f"{relation.replace('_', ' ')} "
                                    f"{cluster_concepts[link_target].canonical_name}"
                                ),
                                keywords=[],
                                delta_weight=1.0,
                                weight_cap=config.edge_weight_cap,
                                edge_description_max_chars=config.edge_description_max_chars,
                            )
                            links_created += 1
                            emit_event(
                                "graph.gardener.link_created",
                                status="info",
                                component="graph",
                                operation="graph.gardener.run",
                                workspace_id=workspace_id,
                                src_id=concept_id,
                                tgt_id=link_target,
                                relation_type=relation,
                                confidence=decision.confidence,
                            )

                    elif decision.decision == "MERGE_INTO" and decision.merge_into_id is not None:
                        target_id = decision.merge_into_id
                        if target_id not in cluster or target_id in already_merged:
                            continue
                        if concept_id not in seed_ids:
                            continue
                        if cluster_concepts[concept_id].has_mastery:
                            emit_event(
                                "graph.gardener.merge.skip",
                                status="info",
                                component="graph",
                                operation="graph.gardener.run",
                                workspace_id=workspace_id,
                                source_id=concept_id,
                                reason="mastery_protection",
                            )
                            continue
                        if _execute_merge(
                            session=session,
                            workspace_id=workspace_id,
                            from_concept_id=concept_id,
                            to_concept_id=target_id,
                            confidence=decision.confidence,
                            method="llm",
                            reason=_GARDENER_REASON,
                            edge_weight_cap=config.edge_weight_cap,
                            edge_description_max_chars=config.edge_description_max_chars,
                        ):
                            merges_applied += 1
                            already_merged.add(concept_id)

                stabilized_seed_ids.update(cluster_seed_ids)

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
            links_created=links_created,
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
            span.set_attribute("graph.links_created", links_created)
            span.set_attribute("graph.llm_calls", budgets.llm_calls)
            span.set_attribute("graph.stopped_by_cluster_budget", stopped_by_cluster_budget)
            span.set_attribute("graph.stopped_by_llm_budget", stopped_by_llm_budget)
            set_span_summary(
                span,
                input_summary=f"workspace={workspace_id}, seeds={len(seeds)}",
                output_summary=(
                    f"processed={budgets.clusters_processed}, merges={merges_applied}, "
                    f"links={links_created}, llm={budgets.llm_calls}"
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
    full_scan: bool = False,
) -> list[CanonicalCandidate]:
    lexical_top_k = config.full_scan_lexical_top_k if full_scan else config.lexical_top_k
    vector_top_k = config.full_scan_vector_top_k if full_scan else config.vector_top_k
    cap = config.full_scan_candidate_cap if full_scan else config.candidate_cap

    lexical = graph_repository.list_lexical_candidates(
        session,
        workspace_id=workspace_id,
        alias=normalize_alias(seed.canonical_name),
        top_k=lexical_top_k,
    )
    vectors: list[graph_repository.CanonicalCandidateRow] = []
    if seed.embedding is not None:
        vectors = graph_repository.list_vector_candidates(
            session,
            workspace_id=workspace_id,
            query_embedding=seed.embedding,
            top_k=vector_top_k,
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
    return ranked[:cap]


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


def _batch_cluster_llm_decisions(
    *,
    llm_client: GraphLLMClient,
    concepts: Mapping[int, _ClusterConcept],
    clusters: list[set[int]],
) -> list[list[tuple[int, _GardenerDecisionPayload | None]]]:
    """Disambiguate clusters: each member is checked against all others.

    Returns one list per cluster. Each list contains (concept_id, decision)
    tuples for every member of that cluster.
    """
    # Build batch items: each cluster member becomes a separate item
    batch_items: list[dict[str, object]] = []
    item_map: list[tuple[int, int]] = []  # (cluster_index, concept_id)

    for cluster_idx, cluster in enumerate(clusters):
        ordered_ids = sorted(cluster)
        for concept_id in ordered_ids:
            concept = concepts[concept_id]
            others = [cid for cid in ordered_ids if cid != concept_id]
            if not others:
                continue
            batch_items.append({
                "raw_name": concept.canonical_name,
                "context_snippet": concept.description,
                "candidates": [
                    {
                        "id": cid,
                        "canonical_name": concepts[cid].canonical_name,
                        "description": concepts[cid].description,
                        "aliases": list(concepts[cid].aliases),
                        "tier": concepts[cid].tier or "unknown",
                        "has_mastery": concepts[cid].has_mastery,
                        "provenance_count": concepts[cid].provenance_count,
                        "neighbors": list(concepts[cid].neighbor_names),
                    }
                    for cid in others
                ],
            })
            item_map.append((cluster_idx, concept_id))

    if not batch_items:
        return [[] for _ in clusters]

    try:
        with observation_context(operation="graph.disambiguate_batch"):
            raw_decisions = llm_client.disambiguate_batch(items=batch_items)

        # Group results back by cluster — each concept may have multiple operations
        results: list[list[tuple[int, _GardenerDecisionPayload | None]]] = [[] for _ in clusters]
        for (cluster_idx, concept_id), raw_dec in zip(item_map, raw_decisions):
            ops = raw_dec.get("operations", [raw_dec]) if isinstance(raw_dec, dict) else [raw_dec]
            parsed_any = False
            for op in ops:
                try:
                    payload = _GardenerDecisionPayload.model_validate(op)
                    if payload.decision != "CREATE_NEW":
                        results[cluster_idx].append((concept_id, payload))
                        parsed_any = True
                except (ValidationError, ValueError):
                    pass
            if not parsed_any:
                results[cluster_idx].append((concept_id, None))
        return results
    except (RuntimeError, ValueError):
        return [[] for _ in clusters]



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
