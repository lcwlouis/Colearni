"""Online resolver for canonical concept/edge upserts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from adapters.db import graph_repository
from core.contracts import EmbeddingProvider, GraphLLMClient
from core.observability import emit_event, observation_context
from core.settings import Settings
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.orm import Session

from domain.graph.resolver_apply import merge_aliases, merge_description, merge_map_method
from domain.graph.resolver_candidates import combine_candidates
from domain.graph.resolver_decision import (
    deterministic_lexical_decision,
    deterministic_vector_decision,
    emit_resolver_budget_usage,
)
from domain.graph.types import (
    CanonicalCandidate,
    ExtractedConcept,
    ExtractedEdge,
    ResolvedConcept,
    ResolverBudgets,
    ResolverDecision,
    dedupe_keywords,
    normalize_alias,
    tier_rank,
    truncate_text,
)


@dataclass(frozen=True, slots=True)
class ResolverConfig:
    """Thresholds and bounded limits for online resolution."""

    lexical_top_k: int
    vector_top_k: int
    candidate_cap: int
    lexical_similarity_threshold: float
    lexical_margin_threshold: float
    vector_similarity_threshold: float
    vector_margin_threshold: float
    llm_confidence_floor: float
    concept_description_max_chars: int
    edge_description_max_chars: int
    edge_weight_cap: float

    @classmethod
    def from_settings(cls, settings: Settings) -> ResolverConfig:
        return cls(
            lexical_top_k=settings.resolver_lexical_top_k,
            vector_top_k=settings.resolver_vector_top_k,
            candidate_cap=settings.resolver_candidate_cap,
            lexical_similarity_threshold=settings.resolver_lexical_similarity_threshold,
            lexical_margin_threshold=settings.resolver_lexical_margin_threshold,
            vector_similarity_threshold=settings.resolver_vector_similarity_threshold,
            vector_margin_threshold=settings.resolver_vector_margin_threshold,
            llm_confidence_floor=settings.resolver_llm_confidence_floor,
            concept_description_max_chars=settings.resolver_concept_description_max_chars,
            edge_description_max_chars=settings.resolver_edge_description_max_chars,
            edge_weight_cap=settings.resolver_edge_weight_cap,
        )


class _DisambiguationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: Literal["MERGE_INTO", "CREATE_NEW"]
    merge_into_id: int | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    alias_to_add: str | None = None
    proposed_description: str | None = None

    @model_validator(mode="after")
    def validate_merge_id(self) -> _DisambiguationPayload:
        if self.decision == "MERGE_INTO" and self.merge_into_id is None:
            raise ValueError("merge_into_id is required when decision=MERGE_INTO")
        return self


class OnlineResolver:
    """Bounded resolver that merges raw concepts/edges into canonical graph rows."""

    def __init__(
        self,
        *,
        session: Session,
        llm_client: GraphLLMClient,
        config: ResolverConfig,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._session = session
        self._llm_client = llm_client
        self._config = config
        self._embedding_provider = embedding_provider

    def resolve_concept(
        self,
        *,
        workspace_id: int,
        chunk_id: int,
        raw_concept: ExtractedConcept,
        budgets: ResolverBudgets,
    ) -> ResolvedConcept:
        """Resolve one raw concept into canonical graph row and persist side-effects."""
        name_norm = normalize_alias(raw_concept.name)
        if not name_norm:
            raise ValueError("raw concept name cannot be empty after normalization")

        exact_match = graph_repository.find_alias_match(
            self._session,
            workspace_id=workspace_id,
            alias=name_norm,
        )
        query_embedding = self._embed_query(
            raw_name=raw_concept.name,
            context=raw_concept.context_snippet,
        )

        if exact_match is not None:
            decision = ResolverDecision(
                decision="MERGE_INTO",
                merge_into_id=exact_match.id,
                confidence=1.0,
                method="exact",
            )
            return self._apply_decision(
                workspace_id=workspace_id,
                chunk_id=chunk_id,
                raw_concept=raw_concept,
                name_norm=name_norm,
                decision=decision,
                query_embedding=query_embedding,
            )

        lexical_rows = graph_repository.list_lexical_candidates(
            self._session,
            workspace_id=workspace_id,
            alias=name_norm,
            top_k=self._config.lexical_top_k,
        )
        vector_rows: list[graph_repository.CanonicalCandidateRow] = []
        if query_embedding is not None:
            vector_rows = graph_repository.list_vector_candidates(
                self._session,
                workspace_id=workspace_id,
                query_embedding=query_embedding,
                top_k=self._config.vector_top_k,
            )
        candidates = self._combine_candidates(lexical_rows=lexical_rows, vector_rows=vector_rows)

        lexical_decision = self._deterministic_lexical_decision(candidates)
        if lexical_decision is not None:
            return self._apply_decision(
                workspace_id=workspace_id,
                chunk_id=chunk_id,
                raw_concept=raw_concept,
                name_norm=name_norm,
                decision=lexical_decision,
                query_embedding=query_embedding,
            )

        vector_decision = self._deterministic_vector_decision(candidates)
        if vector_decision is not None:
            return self._apply_decision(
                workspace_id=workspace_id,
                chunk_id=chunk_id,
                raw_concept=raw_concept,
                name_norm=name_norm,
                decision=vector_decision,
                query_embedding=query_embedding,
            )

        llm_decision = self._llm_disambiguation_decision(
            workspace_id=workspace_id,
            chunk_id=chunk_id,
            raw_concept=raw_concept,
            candidates=candidates,
            budgets=budgets,
        )
        return self._apply_decision(
            workspace_id=workspace_id,
            chunk_id=chunk_id,
            raw_concept=raw_concept,
            name_norm=name_norm,
            decision=llm_decision,
            query_embedding=query_embedding,
        )

    def upsert_edge(
        self,
        *,
        workspace_id: int,
        chunk_id: int,
        raw_edge: ExtractedEdge,
        src_concept_id: int,
        tgt_concept_id: int,
    ) -> int | None:
        """Upsert one canonical edge and attach provenance."""
        if src_concept_id == tgt_concept_id:
            return None

        edge_id = graph_repository.upsert_canonical_edge(
            self._session,
            workspace_id=workspace_id,
            src_id=src_concept_id,
            tgt_id=tgt_concept_id,
            relation_type=raw_edge.relation_type.strip(),
            description=truncate_text(
                raw_edge.description,
                self._config.edge_description_max_chars,
            ),
            keywords=dedupe_keywords(list(raw_edge.keywords)),
            delta_weight=max(0.0, raw_edge.weight),
            weight_cap=self._config.edge_weight_cap,
            edge_description_max_chars=self._config.edge_description_max_chars,
        )
        graph_repository.insert_provenance(
            self._session,
            workspace_id=workspace_id,
            target_type="edge",
            target_id=edge_id,
            chunk_id=chunk_id,
        )
        return edge_id

    def _embed_query(self, *, raw_name: str, context: str) -> list[float] | None:
        if self._embedding_provider is None:
            return None
        query_text = raw_name if not context else f"{raw_name}\n{context}"
        embeddings = self._embedding_provider.embed_texts([query_text])
        if len(embeddings) != 1:
            raise ValueError(
                "Embedding provider must return exactly one embedding for concept query"
            )
        return embeddings[0]

    def _combine_candidates(
        self,
        *,
        lexical_rows: Sequence[graph_repository.CanonicalCandidateRow],
        vector_rows: Sequence[graph_repository.CanonicalCandidateRow],
    ) -> list[CanonicalCandidate]:
        return combine_candidates(
            lexical_rows=lexical_rows,
            vector_rows=vector_rows,
            candidate_cap=self._config.candidate_cap,
        )

    def _deterministic_lexical_decision(
        self,
        candidates: Sequence[CanonicalCandidate],
    ) -> ResolverDecision | None:
        return deterministic_lexical_decision(
            candidates,
            lexical_similarity_threshold=self._config.lexical_similarity_threshold,
            lexical_margin_threshold=self._config.lexical_margin_threshold,
        )

    def _deterministic_vector_decision(
        self,
        candidates: Sequence[CanonicalCandidate],
    ) -> ResolverDecision | None:
        return deterministic_vector_decision(
            candidates,
            vector_similarity_threshold=self._config.vector_similarity_threshold,
            vector_margin_threshold=self._config.vector_margin_threshold,
        )

    def _llm_disambiguation_decision(
        self,
        *,
        workspace_id: int,
        chunk_id: int,
        raw_concept: ExtractedConcept,
        candidates: Sequence[CanonicalCandidate],
        budgets: ResolverBudgets,
    ) -> ResolverDecision:
        emit_resolver_budget_usage(
            workspace_id=workspace_id,
            chunk_id=chunk_id,
            budgets=budgets,
        )
        if not candidates:
            return ResolverDecision(
                decision="CREATE_NEW",
                merge_into_id=None,
                confidence=1.0,
                method="fallback",
            )
        if not budgets.can_call_llm():
            emit_event(
                "graph.resolver.budget.hard_stop",
                status="warning",
                component="graph",
                operation="graph.resolver.resolve_concept",
                workspace_id=workspace_id,
                chunk_id=chunk_id,
                reason=budgets.last_hard_stop_reason or "budget_exhausted",
                llm_calls_chunk=budgets.llm_calls_chunk,
                llm_calls_document=budgets.llm_calls_document,
                max_llm_calls_per_chunk=budgets.max_llm_calls_per_chunk,
                max_llm_calls_per_document=budgets.max_llm_calls_per_document,
            )
            return ResolverDecision(
                decision="CREATE_NEW",
                merge_into_id=None,
                confidence=1.0,
                method="fallback",
            )

        try:
            budgets.register_llm_call()
            emit_resolver_budget_usage(
                workspace_id=workspace_id,
                chunk_id=chunk_id,
                budgets=budgets,
            )
            with observation_context(operation="graph.disambiguate"):
                payload = _DisambiguationPayload.model_validate(
                    self._llm_client.disambiguate(
                        raw_name=raw_concept.name,
                        context_snippet=raw_concept.context_snippet,
                        candidates=[
                            {
                                "id": candidate.concept_id,
                                "canonical_name": candidate.canonical_name,
                                "description": candidate.description,
                                "aliases": list(candidate.aliases),
                            }
                            for candidate in candidates
                        ],
                    )
                )
        except (RuntimeError, ValidationError, ValueError):
            return ResolverDecision(
                decision="CREATE_NEW",
                merge_into_id=None,
                confidence=1.0,
                method="fallback",
                llm_used=True,
            )

        candidate_ids = {candidate.concept_id for candidate in candidates}
        if payload.confidence < self._config.llm_confidence_floor:
            return ResolverDecision(
                decision="CREATE_NEW",
                merge_into_id=None,
                confidence=payload.confidence,
                method="llm",
                alias_to_add=payload.alias_to_add,
                proposed_description=payload.proposed_description,
                llm_used=True,
            )

        if payload.decision == "MERGE_INTO" and payload.merge_into_id in candidate_ids:
            return ResolverDecision(
                decision="MERGE_INTO",
                merge_into_id=payload.merge_into_id,
                confidence=payload.confidence,
                method="llm",
                alias_to_add=payload.alias_to_add,
                proposed_description=payload.proposed_description,
                llm_used=True,
            )

        return ResolverDecision(
            decision="CREATE_NEW",
            merge_into_id=None,
            confidence=payload.confidence,
            method="llm",
            alias_to_add=payload.alias_to_add,
            proposed_description=payload.proposed_description,
            llm_used=True,
        )

    def _apply_decision(
        self,
        *,
        workspace_id: int,
        chunk_id: int,
        raw_concept: ExtractedConcept,
        name_norm: str,
        decision: ResolverDecision,
        query_embedding: Sequence[float] | None,
    ) -> ResolvedConcept:
        if decision.decision == "MERGE_INTO" and decision.merge_into_id is not None:
            canonical = graph_repository.get_canonical_concept(
                self._session,
                workspace_id=workspace_id,
                concept_id=decision.merge_into_id,
            )
            if canonical is not None:
                updated = self._merge_into_existing(
                    workspace_id=workspace_id,
                    chunk_id=chunk_id,
                    raw_concept=raw_concept,
                    canonical=canonical,
                    query_embedding=query_embedding,
                    decision=decision,
                )
                graph_repository.upsert_concept_merge_map(
                    self._session,
                    workspace_id=workspace_id,
                    alias=name_norm,
                    canon_concept_id=updated.id,
                    confidence=decision.confidence,
                    method=merge_map_method(decision.method),
                )
                graph_repository.insert_provenance(
                    self._session,
                    workspace_id=workspace_id,
                    target_type="concept",
                    target_id=updated.id,
                    chunk_id=chunk_id,
                )
                return ResolvedConcept(
                    concept_id=updated.id,
                    created=False,
                    method=decision.method,
                    used_llm=decision.llm_used,
                )

        created_concept, was_created = self._create_or_reuse_canonical(
            workspace_id=workspace_id,
            chunk_id=chunk_id,
            raw_concept=raw_concept,
            query_embedding=query_embedding,
            decision=decision,
        )
        graph_repository.upsert_concept_merge_map(
            self._session,
            workspace_id=workspace_id,
            alias=name_norm,
            canon_concept_id=created_concept.id,
            confidence=decision.confidence if decision.llm_used else 1.0,
            method="llm" if decision.llm_used else "exact",
        )
        graph_repository.insert_provenance(
            self._session,
            workspace_id=workspace_id,
            target_type="concept",
            target_id=created_concept.id,
            chunk_id=chunk_id,
        )
        return ResolvedConcept(
            concept_id=created_concept.id,
            created=was_created,
            method=decision.method,
            used_llm=decision.llm_used,
        )

    def _merge_into_existing(
        self,
        *,
        workspace_id: int,
        chunk_id: int,
        raw_concept: ExtractedConcept,
        canonical: graph_repository.CanonicalConceptRow,
        query_embedding: Sequence[float] | None,
        decision: ResolverDecision,
    ) -> graph_repository.CanonicalConceptRow:
        alias_to_add = (decision.alias_to_add or raw_concept.name).strip()
        merged_aliases = merge_aliases(canonical.aliases, alias_to_add)
        proposed_description = decision.proposed_description or raw_concept.description
        merged_description = merge_description(
            existing=canonical.description,
            proposed=proposed_description,
            max_chars=self._config.concept_description_max_chars,
        )

        merged_embedding = canonical.embedding
        embedding_changed = False
        if merged_embedding is None and query_embedding is not None:
            merged_embedding = list(query_embedding)
            embedding_changed = True

        # Promote tier only if the incoming tier is more specific than existing.
        effective_tier = (
            raw_concept.tier
            if tier_rank(raw_concept.tier) > tier_rank(canonical.tier)
            else canonical.tier
        )

        changed = (
            merged_aliases != canonical.aliases
            or merged_description != canonical.description
            or embedding_changed
            or effective_tier != canonical.tier
        )
        if not changed:
            return canonical

        return graph_repository.update_canonical_concept(
            self._session,
            workspace_id=workspace_id,
            concept_id=canonical.id,
            description=merged_description,
            aliases=merged_aliases,
            embedding=merged_embedding,
            mark_dirty=True,
            tier=effective_tier,
        )

    def _create_or_reuse_canonical(
        self,
        *,
        workspace_id: int,
        chunk_id: int,
        raw_concept: ExtractedConcept,
        query_embedding: Sequence[float] | None,
        decision: ResolverDecision,
    ) -> tuple[graph_repository.CanonicalConceptRow, bool]:
        existing = graph_repository.find_canonical_by_name_ci(
            self._session,
            workspace_id=workspace_id,
            canonical_name=raw_concept.name.strip(),
        )
        if existing is not None:
            return (
                self._merge_into_existing(
                    workspace_id=workspace_id,
                    chunk_id=chunk_id,
                    raw_concept=raw_concept,
                    canonical=existing,
                    query_embedding=query_embedding,
                    decision=decision,
                ),
                False,
            )

        description = truncate_text(
            raw_concept.description or decision.proposed_description,
            self._config.concept_description_max_chars,
        )
        return (
            graph_repository.create_canonical_concept(
                self._session,
                workspace_id=workspace_id,
                canonical_name=raw_concept.name.strip(),
                description=description,
                aliases=[raw_concept.name.strip()],
                embedding=query_embedding,
                tier=raw_concept.tier,
            ),
            True,
        )
