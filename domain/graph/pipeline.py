"""Graph builder pipeline: raw extraction + online canonical resolver."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import uuid4

from adapters.db import graph_repository
from core.contracts import EmbeddingProvider, GraphLLMClient
from core.observability import observation_context, start_span
from core.settings import Settings
from sqlalchemy.orm import Session

from domain.graph.extraction import extract_raw_graph_from_chunk
from domain.graph.resolver import OnlineResolver, ResolverConfig
from domain.graph.types import ExtractedConcept, GraphBuildResult, ResolverBudgets, normalize_alias

if TYPE_CHECKING:
    from adapters.db.chunks import ChunkRow


def build_graph_for_chunks(
    session: Session,
    *,
    workspace_id: int,
    chunks: Sequence["ChunkRow"],
    llm_client: GraphLLMClient,
    settings: Settings,
    embedding_provider: EmbeddingProvider | None = None,
    run_id: str | None = None,
) -> GraphBuildResult:
    """Process chunks into raw graph rows and canonical upserts with provenance."""
    resolved_run_id = run_id or str(uuid4())
    with observation_context(
        component="graph",
        operation="graph.resolver.run",
        workspace_id=workspace_id,
        run_id=resolved_run_id,
    ), start_span(
        "graph.resolver.run",
        component="graph",
        operation="graph.resolver.run",
        workspace_id=workspace_id,
        run_id=resolved_run_id,
    ):
        config = ResolverConfig.from_settings(settings)
        resolver = OnlineResolver(
            session=session,
            llm_client=llm_client,
            config=config,
            embedding_provider=embedding_provider,
        )
        budgets = ResolverBudgets(
            max_llm_calls_per_chunk=settings.resolver_max_llm_calls_per_chunk,
            max_llm_calls_per_document=settings.resolver_max_llm_calls_per_document,
        )

        raw_concepts_written = 0
        raw_edges_written = 0
        canonical_created = 0
        canonical_merged = 0
        canonical_edges_upserted = 0

        for chunk in chunks:
            with observation_context(chunk_id=chunk.id):
                budgets.reset_chunk()
                extraction = extract_raw_graph_from_chunk(
                    llm_client=llm_client,
                    chunk_text=chunk.text,
                    concept_description_max_chars=settings.resolver_concept_description_max_chars,
                    edge_description_max_chars=settings.resolver_edge_description_max_chars,
                )

                raw_concepts_written += graph_repository.insert_raw_concepts(
                    session,
                    workspace_id=workspace_id,
                    chunk_id=chunk.id,
                    concepts=extraction.concepts,
                )
                raw_edges_written += graph_repository.insert_raw_edges(
                    session,
                    workspace_id=workspace_id,
                    chunk_id=chunk.id,
                    edges=extraction.edges,
                )

                resolved_in_chunk: dict[str, int] = {}
                for concept in extraction.concepts:
                    resolved = resolver.resolve_concept(
                        workspace_id=workspace_id,
                        chunk_id=chunk.id,
                        raw_concept=concept,
                        budgets=budgets,
                    )
                    resolved_in_chunk[normalize_alias(concept.name)] = resolved.concept_id
                    if resolved.created:
                        canonical_created += 1
                    else:
                        canonical_merged += 1

                for edge in extraction.edges:
                    src_id = _resolve_edge_endpoint(
                        resolver=resolver,
                        workspace_id=workspace_id,
                        chunk_id=chunk.id,
                        concept_name=edge.src_name,
                        chunk_text=chunk.text,
                        resolved_in_chunk=resolved_in_chunk,
                        budgets=budgets,
                    )
                    tgt_id = _resolve_edge_endpoint(
                        resolver=resolver,
                        workspace_id=workspace_id,
                        chunk_id=chunk.id,
                        concept_name=edge.tgt_name,
                        chunk_text=chunk.text,
                        resolved_in_chunk=resolved_in_chunk,
                        budgets=budgets,
                    )
                    edge_id = resolver.upsert_edge(
                        workspace_id=workspace_id,
                        chunk_id=chunk.id,
                        raw_edge=edge,
                        src_concept_id=src_id,
                        tgt_concept_id=tgt_id,
                    )
                    if edge_id is not None:
                        canonical_edges_upserted += 1

        return GraphBuildResult(
            raw_concepts_written=raw_concepts_written,
            raw_edges_written=raw_edges_written,
            canonical_created=canonical_created,
            canonical_merged=canonical_merged,
            canonical_edges_upserted=canonical_edges_upserted,
            llm_disambiguations=budgets.llm_calls_document,
        )


def _resolve_edge_endpoint(
    *,
    resolver: OnlineResolver,
    workspace_id: int,
    chunk_id: int,
    concept_name: str,
    chunk_text: str,
    resolved_in_chunk: dict[str, int],
    budgets: ResolverBudgets,
) -> int:
    alias_norm = normalize_alias(concept_name)
    existing = resolved_in_chunk.get(alias_norm)
    if existing is not None:
        return existing

    resolved = resolver.resolve_concept(
        workspace_id=workspace_id,
        chunk_id=chunk_id,
        raw_concept=ExtractedConcept(
            name=concept_name,
            context_snippet=chunk_text,
            description="",
        ),
        budgets=budgets,
    )
    resolved_in_chunk[alias_norm] = resolved.concept_id
    return resolved.concept_id
