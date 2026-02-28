"""Post-ingest background tasks – embeddings, summary, graph extraction."""

from __future__ import annotations

import logging

from adapters.db.chunks import list_chunks_for_document
from adapters.db.documents import update_document_summary, update_document_status
from adapters.embeddings.factory import build_embedding_provider
from domain.embeddings.pipeline import NewChunkInput, populate_new_chunk_embeddings
from domain.graph.pipeline import build_graph_for_chunks

from core.contracts import EmbeddingProvider, GraphLLMClient
from core.observability import (
    SPAN_KIND_CHAIN,
    observation_context,
    set_span_kind,
    start_span,
)
from core.prompting import PromptRegistry
from core.settings import Settings, get_settings

_log = logging.getLogger(__name__)
_registry = PromptRegistry()


def generate_document_summary(
    *,
    chunks: list[str],
    llm_client: GraphLLMClient,
    max_chunks: int = 5,
    max_chars: int = 3000,
) -> str | None:
    """Generate a short 2-3 sentence summary from the first few chunks."""
    if not chunks:
        return None
    sample_text = ""
    for chunk in chunks[:max_chunks]:
        if len(sample_text) + len(chunk) > max_chars:
            remaining = max_chars - len(sample_text)
            if remaining > 100:
                sample_text += chunk[:remaining]
            break
        sample_text += chunk + "\n\n"
    if not sample_text.strip():
        return None
    prompt, prompt_meta = _build_document_summary_prompt(sample_text.strip())
    try:
        summary = llm_client.generate_tutor_text(prompt=prompt, prompt_meta=prompt_meta).strip()
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
            component="ingestion",
            operation="post_ingest",
            workspace_id=workspace_id,
            document_id=document_id,
        ) as span:
            set_span_kind(span, SPAN_KIND_CHAIN)

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
                except Exception:
                    _log.exception("Background embedding population failed doc=%s", document_id)
                    db.rollback()

        # 2) Summary + graph
        if active_settings.ingest_build_graph and graph_llm_client is not None:
            _log.info("post_ingest summary+graph START doc=%s", document_id)
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
            except Exception as exc:
                _log.exception("Background graph extraction failed doc=%s", document_id)
                update_document_status(
                    db, workspace_id=workspace_id, document_id=document_id,
                    graph_status="failed",
                    error_message=f"Graph extraction failed: {exc}",
                )

        db.commit()
        _log.info("post_ingest_tasks DONE ws=%s doc=%s", workspace_id, document_id)
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


def _build_document_summary_prompt(sample_text: str) -> tuple[str, Any]:
    """Build the document summary prompt from asset or inline fallback."""
    try:
        return _registry.render_with_meta("document_document_summary_v1", {
            "chunks": sample_text,
        })
    except Exception:
        _log.debug("asset render failed for document_summary_v1, using inline fallback")
        return (
            "Summarize the following document excerpt in 2-3 concise sentences. "
            "Focus on the main topics and key concepts covered.\n\n"
            f"DOCUMENT EXCERPT:\n{sample_text}\n\n"
            "SUMMARY:"
        ), None
