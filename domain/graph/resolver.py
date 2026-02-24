"""Online resolver for canonical concept/edge upserts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from adapters.db import graph_repository
from core.contracts import EmbeddingProvider, GraphLLMClient
from core.settings import Settings
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.orm import Session

from domain.graph.types import (
    CanonicalCandidate,
    ExtractedConcept,
    ExtractedEdge,
    ResolvedConcept,
    ResolverBudgets,
    ResolverDecision,
    dedupe_keywords,
    normalize_alias,
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
        by_id: dict[int, CanonicalCandidate] = {}

        for row in lexical_rows:
            by_id[row.id] = CanonicalCandidate(
                concept_id=row.id,
                canonical_name=row.canonical_name,
                description=row.description,
                aliases=tuple(row.aliases),
                lexical_similarity=row.lexical_similarity,
                vector_similarity=None,
            )

        for row in vector_rows:
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
                concept_id=existing.concept_id,
                canonical_name=existing.canonical_name,
                description=existing.description,
                aliases=existing.aliases,
                lexical_similarity=existing.lexical_similarity,
                vector_similarity=row.vector_similarity,
            )

        ranked_candidates = sorted(
            by_id.values(),
            key=lambda candidate: (
                max(
                    candidate.lexical_similarity or 0.0,
                    candidate.vector_similarity or 0.0,
                ),
                candidate.lexical_similarity or -1.0,
                candidate.vector_similarity or -1.0,
                -candidate.concept_id,
            ),
            reverse=True,
        )
        return ranked_candidates[: self._config.candidate_cap]

    def _deterministic_lexical_decision(
        self,
        candidates: Sequence[CanonicalCandidate],
    ) -> ResolverDecision | None:
        lexical_ranked = sorted(
            [candidate for candidate in candidates if candidate.lexical_similarity is not None],
            key=lambda candidate: candidate.lexical_similarity or -1.0,
            reverse=True,
        )
        if not lexical_ranked:
            return None

        best = float(lexical_ranked[0].lexical_similarity or 0.0)
        second = (
            float(lexical_ranked[1].lexical_similarity or 0.0)
            if len(lexical_ranked) > 1
            else 0.0
        )
        margin = best - second
        if (
            best >= self._config.lexical_similarity_threshold
            and margin >= self._config.lexical_margin_threshold
        ):
            return ResolverDecision(
                decision="MERGE_INTO",
                merge_into_id=lexical_ranked[0].concept_id,
                confidence=min(1.0, best),
                method="lexical",
            )
        return None

    def _deterministic_vector_decision(
        self,
        candidates: Sequence[CanonicalCandidate],
    ) -> ResolverDecision | None:
        vector_ranked = sorted(
            [candidate for candidate in candidates if candidate.vector_similarity is not None],
            key=lambda candidate: candidate.vector_similarity or -1.0,
            reverse=True,
        )
        if not vector_ranked:
            return None

        best = float(vector_ranked[0].vector_similarity or 0.0)
        second = float(vector_ranked[1].vector_similarity or 0.0) if len(vector_ranked) > 1 else 0.0
        margin = best - second
        if (
            best >= self._config.vector_similarity_threshold
            and margin >= self._config.vector_margin_threshold
        ):
            return ResolverDecision(
                decision="MERGE_INTO",
                merge_into_id=vector_ranked[0].concept_id,
                confidence=min(1.0, best),
                method="vector",
            )
        return None

    def _llm_disambiguation_decision(
        self,
        *,
        raw_concept: ExtractedConcept,
        candidates: Sequence[CanonicalCandidate],
        budgets: ResolverBudgets,
    ) -> ResolverDecision:
        if not candidates or not budgets.can_call_llm():
            return ResolverDecision(
                decision="CREATE_NEW",
                merge_into_id=None,
                confidence=1.0,
                method="fallback",
            )

        try:
            budgets.register_llm_call()
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
                    method=_merge_map_method(decision.method),
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
        merged_aliases = _merge_aliases(canonical.aliases, alias_to_add)
        proposed_description = decision.proposed_description or raw_concept.description
        merged_description = _merge_description(
            existing=canonical.description,
            proposed=proposed_description,
            max_chars=self._config.concept_description_max_chars,
        )

        merged_embedding = canonical.embedding
        embedding_changed = False
        if merged_embedding is None and query_embedding is not None:
            merged_embedding = list(query_embedding)
            embedding_changed = True

        changed = (
            merged_aliases != canonical.aliases
            or merged_description != canonical.description
            or embedding_changed
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
            ),
            True,
        )


def _merge_map_method(method: str) -> str:
    if method in {"exact", "lexical", "vector", "llm", "manual"}:
        return method
    return "exact"


def _merge_aliases(existing_aliases: Sequence[str], alias_to_add: str) -> list[str]:
    candidate = alias_to_add.strip()
    if not candidate:
        return list(existing_aliases)
    normalized_existing = {normalize_alias(alias) for alias in existing_aliases}
    if normalize_alias(candidate) in normalized_existing:
        return list(existing_aliases)
    return [*existing_aliases, candidate]


def _merge_description(*, existing: str, proposed: str | None, max_chars: int) -> str:
    bounded_existing = truncate_text(existing, max_chars)
    bounded_proposed = truncate_text(proposed, max_chars)
    if not bounded_existing:
        return bounded_proposed
    if not bounded_proposed:
        return bounded_existing
    return bounded_proposed if len(bounded_proposed) > len(bounded_existing) else bounded_existing
