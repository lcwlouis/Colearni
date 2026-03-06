"""Post-ingest background tasks – embeddings, summary, graph extraction."""

from __future__ import annotations

import logging
from typing import Any

from adapters.db.chunks import list_chunks_for_document
from adapters.db.documents import update_document_status, update_document_summary
from adapters.embeddings.factory import build_embedding_provider
from core.contracts import EmbeddingProvider, GraphLLMClient
from core.observability import (
    SPAN_KIND_CHAIN,
    observation_context,
    set_span_summary,
    start_span,
)
from core.prompting import PromptRegistry
from core.settings import Settings, get_settings
from core.tokenization import count_text_tokens
from domain.embeddings.pipeline import NewChunkInput, populate_new_chunk_embeddings
from domain.graph.pipeline import build_graph_for_chunks

_log = logging.getLogger(__name__)
_registry = PromptRegistry()


def generate_document_summary(
    *,
    chunks: list[str],
    llm_client: GraphLLMClient,
    max_chunks: int = 50,
    max_tokens: int = 8000,
    model: str = "gpt-4o-mini",
) -> str | None:
    """Generate a short 2-3 sentence summary from the first few chunks."""
    if not chunks:
        return None
    sample_text = ""
    for chunk in chunks[:max_chunks]:
        candidate = sample_text + chunk + "\n\n"
        if count_text_tokens(candidate, model) > max_tokens:
            remaining_tokens = max_tokens - count_text_tokens(sample_text, model)
            if remaining_tokens > 20:
                sample_text += chunk + "\n\n"
            break
        sample_text = candidate
    if not sample_text.strip():
        return None
    system_prompt, prompt, prompt_meta = _build_document_summary_prompt(sample_text.strip())
    try:
        summary = llm_client.generate_tutor_text(
            prompt=prompt, prompt_meta=prompt_meta, system_prompt=system_prompt
        ).strip()
        if summary and len(summary) > 10:
            return summary[:500]
    except (RuntimeError, ValueError):
        pass
    return None


def run_post_ingest_tasks(
    *,
    workspace_id: int,
    document_id: int,
    graph_llm_client: GraphLLMClient | None = None,
    graph_embedding_provider: EmbeddingProvider | None = None,
    chunk_embedding_provider: EmbeddingProvider | None = None,
    settings: Settings | None = None,
) -> None:
    """Background task: populate embeddings, generate summary, build graph.

    Creates its own DB session so it can run outside the request lifecycle.
    """
    from adapters.db.session import new_session

    _log.info("post_ingest_tasks START ws=%s doc=%s", workspace_id, document_id)
    active_settings = settings or get_settings()
    db = new_session()
    try:
        with observation_context(
            component="ingestion",
            operation="post_ingest",
            workspace_id=workspace_id,
        ), start_span(
            "ingestion.post_ingest",
            kind=SPAN_KIND_CHAIN,
            component="ingestion",
            operation="post_ingest",
            workspace_id=workspace_id,
            document_id=document_id,
        ) as span:
            # Mark graph as extracting
            if active_settings.ingest_build_graph and graph_llm_client is not None:
                update_document_status(
                    db, workspace_id=workspace_id, document_id=document_id,
                    graph_status="extracting",
                )
                db.commit()

            chunks_rows = list_chunks_for_document(
                db,
                workspace_id=workspace_id,
                document_id=document_id,
            )
            chunk_texts = [c.text for c in chunks_rows]
            _log.info("post_ingest loaded %d chunks for doc=%s", len(chunk_texts), document_id)
            set_span_summary(
                span,
                input_summary=f"doc={document_id}, chunks={len(chunk_texts)}",
            )

            # 1) Populate embeddings
            if active_settings.ingest_populate_embeddings:
                provider = chunk_embedding_provider
                if provider is None:
                    try:
                        provider = build_embedding_provider(settings=active_settings)
                    except ValueError:
                        _log.warning("Chunk embedding provider unavailable for background task")
                        provider = None
                if provider is not None:
                    with start_span(
                        "ingestion.embed_chunks",
                        kind=SPAN_KIND_CHAIN,
                        component="ingestion",
                        operation="ingestion.embed_chunks",
                        document_id=document_id,
                    ) as embed_span:
                        if embed_span is not None:
                            set_span_summary(embed_span, input_summary=f"{len(chunk_texts)} chunks")
                        _log.info("post_ingest embedding START doc=%s chunks=%d", document_id, len(chunk_texts))
                        try:
                            populate_new_chunk_embeddings(
                                session=db,
                                provider=provider,
                                chunks=[
                                    NewChunkInput(
                                        workspace_id=workspace_id,
                                        document_id=document_id,
                                        chunk_index=i,
                                        text=chunk_texts[i],
                                    )
                                    for i in range(len(chunk_texts))
                                ],
                                batch_size=active_settings.embedding_batch_size,
                            )
                            _log.info("post_ingest embedding DONE doc=%s", document_id)
                            if embed_span is not None:
                                set_span_summary(embed_span, output_summary=f"{len(chunk_texts)} embedded")
                        except Exception:
                            _log.exception("Background embedding population failed doc=%s", document_id)
                            db.rollback()

            # 2) Summary (runs whenever an LLM client is available)
            if graph_llm_client is not None:
                with start_span(
                    "ingestion.summarize",
                    kind=SPAN_KIND_CHAIN,
                    component="ingestion",
                    operation="ingestion.summarize",
                    document_id=document_id,
                ) as summary_span:
                    _log.info("post_ingest summary START doc=%s", document_id)
                    summary = generate_document_summary(
                        chunks=chunk_texts,
                        llm_client=graph_llm_client,
                    )
                    if summary:
                        _log.info("post_ingest summary generated doc=%s len=%d", document_id, len(summary))
                        update_document_summary(
                            db,
                            workspace_id=workspace_id,
                            document_id=document_id,
                            summary=summary,
                        )
                    if summary_span is not None:
                        s_status = "generated" if summary else "none"
                        s_len = len(summary) if summary else 0
                        set_span_summary(
                            summary_span,
                            output_summary=f"summary={s_status}, len={s_len}",
                        )

            # 3) Graph extraction (only when graph building is enabled)
            if active_settings.ingest_build_graph and graph_llm_client is not None:
                with start_span(
                    "ingestion.build_graph",
                    kind=SPAN_KIND_CHAIN,
                    component="ingestion",
                    operation="ingestion.build_graph",
                    document_id=document_id,
                ) as graph_span:
                    if graph_span is not None:
                        set_span_summary(graph_span, input_summary=f"{len(chunks_rows)} chunks")
                    _log.info("post_ingest graph START doc=%s", document_id)
                    effective_graph_embedding_provider = (
                        graph_embedding_provider or chunk_embedding_provider
                    )
                    try:
                        build_graph_for_chunks(
                            db,
                            workspace_id=workspace_id,
                            chunks=chunks_rows,
                            llm_client=graph_llm_client,
                            settings=active_settings,
                            embedding_provider=effective_graph_embedding_provider,
                        )
                        update_document_status(
                            db, workspace_id=workspace_id, document_id=document_id,
                            graph_status="extracted",
                        )
                        _log.info("post_ingest graph DONE doc=%s", document_id)
                        if graph_span is not None:
                            set_span_summary(graph_span, output_summary="extracted")
                    except Exception as exc:
                        _log.exception("Background graph extraction failed doc=%s", document_id)
                        update_document_status(
                            db, workspace_id=workspace_id, document_id=document_id,
                            graph_status="failed",
                            error_message=f"Graph extraction failed: {exc}",
                        )

            db.commit()
            _log.info("post_ingest_tasks DONE ws=%s doc=%s", workspace_id, document_id)
            set_span_summary(
                span,
                output_summary=f"chunks={len(chunk_texts)}, graph={'yes' if active_settings.ingest_build_graph else 'no'}",
            )
    except Exception as exc:
        _log.exception("Post-ingest background task failed ws=%s doc=%s", workspace_id, document_id)
        db.rollback()
        try:
            db2 = new_session()
            update_document_status(
                db2, workspace_id=workspace_id, document_id=document_id,
                graph_status="failed",
                error_message=f"Post-ingest task failed: {exc}",
            )
            db2.commit()
            db2.close()
        except Exception:
            _log.exception("Failed to record error status doc=%s", document_id)
    finally:
        db.close()


def _build_document_summary_prompt(sample_text: str) -> tuple[str, str, Any]:
    """Return (system_prompt, user_prompt, prompt_meta)."""
    try:
        system_prompt = _registry.render("document_document_summary_v1_system", {})
    except Exception:
        system_prompt = (
            "You are a document summarizer for a learning platform. "
            "Summarize document excerpts in 2-3 concise sentences. "
            "Focus on the main topics and key concepts covered."
        )
    try:
        user_prompt, prompt_meta = _registry.render_with_meta("document_document_summary_v1", {
            "chunks": sample_text,
        })
        return system_prompt, user_prompt, prompt_meta
    except Exception:
        _log.debug("asset render failed for document_summary_v1, using inline fallback")
        return system_prompt, f"DOCUMENT EXCERPT:\n{sample_text}", None
