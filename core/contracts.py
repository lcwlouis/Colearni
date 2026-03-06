"""Core protocol contracts shared across layers."""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Any, Protocol

from core.schemas.assistant import GenerationTrace

if TYPE_CHECKING:
    from domain.retrieval.types import RankedChunk


class EmbeddingProvider(Protocol):
    """Protocol for embedding model adapters."""

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""


class ChunkRetriever(Protocol):
    """Protocol for chunk retrieval implementations."""

    def retrieve(self, query: str, workspace_id: int, top_k: int) -> list["RankedChunk"]:
        """Return ranked chunk matches for a query within one workspace."""


class GraphLLMClient(Protocol):
    """Protocol for LLM-based graph extraction and disambiguation."""

    def extract_raw_graph(self, *, chunk_text: str) -> Mapping[str, Any]:
        """Extract schema-shaped concept and edge candidates from a chunk."""

    def disambiguate(
        self,
        *,
        raw_name: str,
        context_snippet: str | None,
        candidates: Sequence[Mapping[str, object]],
    ) -> Mapping[str, Any]:
        """Choose merge target vs create-new from bounded candidate set."""

    def disambiguate_batch(
        self,
        *,
        items: Sequence[Mapping[str, object]],
    ) -> Sequence[Mapping[str, Any]]:
        """Disambiguate multiple concepts in a single LLM call.

        Each item has keys: raw_name, context_snippet, candidates.
        Returns a list of dicts in input order.  Each dict has:
        ``concept_ref`` (the raw_name) and ``operations`` (a list of
        decision dicts — one concept may map to multiple operations,
        e.g. LINK_ONLY to several targets).
        """

    def generate_tutor_text(
        self,
        *,
        prompt: str,
        prompt_meta: Any | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Generate tutor-facing response text from an instruction prompt."""


class TutorTextStream:
    """Wraps streaming tutor text generation with terminal trace capture.

    Iterate for text delta strings.  After iteration completes, ``.trace``
    holds the normalised ``GenerationTrace``.
    """

    def __init__(
        self,
        delta_iter: Iterator[str],
        *,
        provider: str,
        model: str,
        reasoning_requested: bool = False,
        reasoning_supported: bool = False,
        reasoning_used: bool = False,
        reasoning_effort: str | None = None,
        reasoning_effort_source: str | None = None,
    ) -> None:
        self._delta_iter = delta_iter
        self._provider = provider
        self._model = model
        self._start_ns = time.monotonic_ns()
        self.trace: GenerationTrace = GenerationTrace(
            provider=provider,
            model=model,
            reasoning_requested=reasoning_requested,
            reasoning_supported=reasoning_supported,
            reasoning_used=reasoning_used,
            reasoning_effort=reasoning_effort,
            reasoning_effort_source=reasoning_effort_source,
        )

    def __iter__(self) -> Iterator[str]:
        for chunk in self._delta_iter:
            yield chunk
        elapsed_ms = (time.monotonic_ns() - self._start_ns) / 1_000_000
        self.trace = self.trace.model_copy(update={"timing_ms": round(elapsed_ms, 2)})

    def set_usage(
        self,
        *,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        reasoning_tokens: int | None = None,
        cached_tokens: int | None = None,
        reasoning_content: str | None = None,
    ) -> None:
        """Called by the provider adapter after streaming completes."""
        if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens
        self.trace = self.trace.model_copy(
            update={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "reasoning_tokens": reasoning_tokens,
                "cached_tokens": cached_tokens,
                "reasoning_content": reasoning_content,
            }
        )


class StreamingLLMClient(Protocol):
    """Protocol for LLM clients that support streaming tutor text generation."""

    def generate_tutor_text_stream(
        self,
        *,
        prompt: str,
        prompt_meta: Any | None = None,
        reasoning_effort_override: str | None = None,
        operation: str | None = None,
        system_prompt: str | None = None,
    ) -> TutorTextStream:
        """Stream tutor-facing response text, yielding text deltas."""
