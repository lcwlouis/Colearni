"""Graph builder pipeline: raw extraction + online canonical resolver."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING
from uuid import uuid4

from adapters.db import graph_repository
from core.contracts import EmbeddingProvider, GraphLLMClient
from core.observability import SPAN_KIND_CHAIN, observation_context, set_span_summary, start_span
from core.settings import Settings
from sqlalchemy.orm import Session

from domain.graph.extraction import extract_raw_graph_from_chunk
from domain.graph.resolver import OnlineResolver, ResolverConfig
from domain.graph.types import GraphBuildResult, ResolverBudgets, normalize_alias

if TYPE_CHECKING:
    from adapters.db.chunks import ChunkRow


def _make_graph_windows(
    chunks: "Sequence[ChunkRow]",
    graph_chunk_size: int,
    size_unit: str = "words",
) -> "list[tuple[int, str]]":
    """Batch adjacent vector chunks into larger text windows for graph extraction.

    If *graph_chunk_size* is 0, each chunk becomes its own window (current behaviour).
    Returns a list of ``(representative_chunk_id, window_text)`` tuples.
    The representative chunk id is the first chunk id in each batch.
    """
    def _measure(text: str) -> int:
        return len(text.split()) if size_unit == "words" else len(text)

    if graph_chunk_size <= 0:
        return [(c.id, c.text) for c in chunks]

    windows: list[tuple[int, str]] = []
    batch_ids: list[int] = []
    batch_texts: list[str] = []
    batch_size = 0

    for chunk in chunks:
        if batch_size + _measure(chunk.text) > graph_chunk_size and batch_texts:
            windows.append((batch_ids[0], "\n\n".join(batch_texts)))
            batch_ids = []
            batch_texts = []
            batch_size = 0
        batch_ids.append(chunk.id)
        batch_texts.append(chunk.text)
        batch_size += _measure(chunk.text)

    if batch_texts:
        windows.append((batch_ids[0], "\n\n".join(batch_texts)))

    return windows


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
        kind=SPAN_KIND_CHAIN,
        component="graph",
        operation="graph.resolver.run",
        workspace_id=workspace_id,
        run_id=resolved_run_id,
    ) as span:
        if span is not None:
            span.set_attribute("graph.chunk_count", len(chunks))
            set_span_summary(span, input_summary=f"{len(chunks)} chunks")
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

        windows = _make_graph_windows(chunks, settings.ingest_graph_chunk_size, settings.ingest_chunk_unit)
        if span is not None:
            print("graph.windows_count: ", len(windows))
            for i, (chunk_id, window_text) in enumerate(windows):
                print(f"graph.window_{i}_chunk_id: {chunk_id}")
                print(f"graph.window_{i}_text: {window_text}")
                print(f"*"*40)
        for window_chunk_id, window_text in windows:
            with observation_context(chunk_id=window_chunk_id), start_span(
                "graph.resolver.chunk",
                kind=SPAN_KIND_CHAIN,
                chunk_id=window_chunk_id,
            ) as chunk_span:
                budgets.reset_chunk()
                extraction = extract_raw_graph_from_chunk(
                    llm_client=llm_client,
                    chunk_text=window_text,
                    concept_description_max_chars=settings.resolver_concept_description_max_chars,
                    edge_description_max_chars=settings.resolver_edge_description_max_chars,
                )
                if chunk_span is not None:
                    chunk_span.set_attribute("graph.concepts_extracted", len(extraction.concepts))
                    chunk_span.set_attribute("graph.edges_extracted", len(extraction.edges))

                raw_concepts_written += graph_repository.insert_raw_concepts(
                    session,
                    workspace_id=workspace_id,
                    chunk_id=window_chunk_id,
                    concepts=extraction.concepts,
                )
                raw_edges_written += graph_repository.insert_raw_edges(
                    session,
                    workspace_id=workspace_id,
                    chunk_id=window_chunk_id,
                    edges=extraction.edges,
                )

                resolved_in_chunk: dict[str, int] = {}
                resolved_list = resolver.resolve_concepts_batch(
                    workspace_id=workspace_id,
                    chunk_id=window_chunk_id,
                    raw_concepts=extraction.concepts,
                    budgets=budgets,
                )
                for concept, resolved in zip(extraction.concepts, resolved_list):
                    resolved_in_chunk[normalize_alias(concept.name)] = resolved.concept_id
                    if resolved.created:
                        canonical_created += 1
                    else:
                        canonical_merged += 1

                for edge in extraction.edges:
                    src_id = _resolve_edge_endpoint(
                        resolver=resolver,
                        workspace_id=workspace_id,
                        chunk_id=window_chunk_id,
                        concept_name=edge.src_name,
                        chunk_text=window_text,
                        resolved_in_chunk=resolved_in_chunk,
                        budgets=budgets,
                    )
                    tgt_id = _resolve_edge_endpoint(
                        resolver=resolver,
                        workspace_id=workspace_id,
                        chunk_id=window_chunk_id,
                        concept_name=edge.tgt_name,
                        chunk_text=window_text,
                        resolved_in_chunk=resolved_in_chunk,
                        budgets=budgets,
                    )
                    if src_id is None or tgt_id is None:
                        continue  # skip edge if either endpoint is not a known concept
                    edge_id = resolver.upsert_edge(
                        workspace_id=workspace_id,
                        chunk_id=window_chunk_id,
                        raw_edge=edge,
                        src_concept_id=src_id,
                        tgt_concept_id=tgt_id,
                    )
                    if edge_id is not None:
                        canonical_edges_upserted += 1

        result = GraphBuildResult(
            raw_concepts_written=raw_concepts_written,
            raw_edges_written=raw_edges_written,
            canonical_created=canonical_created,
            canonical_merged=canonical_merged,
            canonical_edges_upserted=canonical_edges_upserted,
            llm_disambiguations=budgets.llm_calls_document,
        )
        if span is not None:
            span.set_attribute("graph.chunks_processed", len(chunks))
            span.set_attribute("graph.windows_processed", len(windows))
            span.set_attribute("graph.canonical_created", canonical_created)
            span.set_attribute("graph.canonical_merged", canonical_merged)
            span.set_attribute("graph.llm_disambiguations", budgets.llm_calls_document)
            span.set_attribute("graph.raw_concepts_written", raw_concepts_written)
            span.set_attribute("graph.raw_edges_written", raw_edges_written)
            set_span_summary(
                span,
                output_summary=(
                    f"chunks={len(chunks)}, created={canonical_created}, "
                    f"merged={canonical_merged}, llm={budgets.llm_calls_document}"
                ),
            )
        return result


def _resolve_edge_endpoint(
    *,
    resolver: OnlineResolver,
    workspace_id: int,
    chunk_id: int,
    concept_name: str,
    chunk_text: str,
    resolved_in_chunk: dict[str, int],
    budgets: ResolverBudgets,
) -> int | None:
    alias_norm = normalize_alias(concept_name)
    return resolved_in_chunk.get(alias_norm)
