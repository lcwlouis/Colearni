"""Unit tests for online graph resolver decisions and budget guards."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from adapters.db import graph_repository
from core.contracts import EmbeddingProvider, GraphLLMClient
from core.observability import configure_observability, set_event_sink
from core.settings import get_settings
from domain.graph.resolver import OnlineResolver, ResolverConfig
from domain.graph.types import ExtractedConcept, ExtractedEdge, ResolverBudgets


class StubLLM(GraphLLMClient):
    """Disambiguation stub with configurable behavior."""

    def __init__(self, disambiguation_payload: Mapping[str, Any] | Exception) -> None:
        self._disambiguation_payload = disambiguation_payload
        self.disambiguate_calls = 0

    def extract_raw_graph(self, *, chunk_text: str) -> Mapping[str, Any]:
        return {"concepts": [], "edges": []}

    def disambiguate(
        self,
        *,
        raw_name: str,
        context_snippet: str | None,
        candidates: Sequence[Mapping[str, object]],
    ) -> Mapping[str, Any]:
        self.disambiguate_calls += 1
        if isinstance(self._disambiguation_payload, Exception):
            raise self._disambiguation_payload
        return self._disambiguation_payload


class StubEmbeddingProvider(EmbeddingProvider):
    """Embedding stub returning one deterministic vector per query."""

    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector for _ in texts]


def _resolver(
    llm: GraphLLMClient,
    *,
    embedding_provider: EmbeddingProvider | None = None,
) -> OnlineResolver:
    return OnlineResolver(
        session=object(),  # not used because repository access is monkeypatched in tests
        llm_client=llm,
        embedding_provider=embedding_provider,
        config=ResolverConfig(
            lexical_top_k=5,
            vector_top_k=10,
            candidate_cap=10,
            lexical_similarity_threshold=0.85,
            lexical_margin_threshold=0.10,
            vector_similarity_threshold=0.92,
            vector_margin_threshold=0.06,
            llm_confidence_floor=0.65,
            concept_description_max_chars=500,
            edge_description_max_chars=300,
            edge_weight_cap=10.0,
        ),
    )


def _concept_row(
    concept_id: int,
    *,
    aliases: list[str] | None = None,
    description: str = "desc",
) -> graph_repository.CanonicalConceptRow:
    return graph_repository.CanonicalConceptRow(
        id=concept_id,
        workspace_id=1,
        canonical_name=f"Concept {concept_id}",
        description=description,
        aliases=aliases or [f"Concept {concept_id}"],
        embedding=None,
        is_active=True,
        dirty=False,
    )


def _candidate_row(
    concept_id: int,
    *,
    lexical: float | None = None,
    vector: float | None = None,
) -> graph_repository.CanonicalCandidateRow:
    return graph_repository.CanonicalCandidateRow(
        id=concept_id,
        canonical_name=f"Concept {concept_id}",
        description=f"description {concept_id}",
        aliases=[f"Concept {concept_id}"],
        lexical_similarity=lexical,
        vector_similarity=vector,
    )


def _patch_repo_defaults(
    monkeypatch: pytest.MonkeyPatch,
    *,
    canonical_row: graph_repository.CanonicalConceptRow | None = None,
) -> dict[str, Any]:
    calls: dict[str, Any] = {"upsert_map": [], "provenance": [], "updated": []}

    monkeypatch.setattr(graph_repository, "find_alias_match", lambda *args, **kwargs: None)
    monkeypatch.setattr(graph_repository, "list_lexical_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(graph_repository, "list_vector_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        graph_repository,
        "get_canonical_concept",
        lambda *args, **kwargs: canonical_row,
    )
    monkeypatch.setattr(
        graph_repository,
        "find_canonical_by_name_ci",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        graph_repository,
        "create_canonical_concept",
        lambda *args, **kwargs: _concept_row(999, aliases=["new concept"]),
    )

    def _record_update(*args, **kwargs):  # noqa: ANN001, ANN202
        calls["updated"].append(kwargs)
        return _concept_row(
            kwargs["concept_id"],
            aliases=list(kwargs["aliases"]),
            description=kwargs["description"],
        )

    monkeypatch.setattr(graph_repository, "update_canonical_concept", _record_update)

    def _record_map(*args, **kwargs):  # noqa: ANN001, ANN202
        calls["upsert_map"].append(kwargs)
        return None

    monkeypatch.setattr(graph_repository, "upsert_concept_merge_map", _record_map)

    def _record_prov(*args, **kwargs):  # noqa: ANN001, ANN202
        calls["provenance"].append(kwargs)
        return None

    monkeypatch.setattr(graph_repository, "insert_provenance", _record_prov)
    return calls


def test_exact_alias_merge_skips_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exact alias matches should merge immediately without LLM disambiguation."""
    llm = StubLLM({"decision": "CREATE_NEW", "confidence": 1.0})
    resolver = _resolver(llm)
    canonical = _concept_row(11, aliases=["existing", "vector space"])
    calls = _patch_repo_defaults(monkeypatch, canonical_row=canonical)
    monkeypatch.setattr(graph_repository, "find_alias_match", lambda *args, **kwargs: canonical)

    resolved = resolver.resolve_concept(
        workspace_id=1,
        chunk_id=2,
        raw_concept=ExtractedConcept(name="Vector Space", context_snippet="ctx", description=""),
        budgets=ResolverBudgets(max_llm_calls_per_chunk=3, max_llm_calls_per_document=50),
    )

    assert resolved.concept_id == 11
    assert resolved.created is False
    assert resolved.method == "exact"
    assert llm.disambiguate_calls == 0
    assert len(calls["upsert_map"]) == 1
    assert len(calls["provenance"]) == 1


def test_lexical_threshold_and_margin_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lexical strong hit should merge without vector/LLM calls."""
    llm = StubLLM({"decision": "CREATE_NEW", "confidence": 1.0})
    resolver = _resolver(llm)
    canonical = _concept_row(21, aliases=["Concept 21", "Vector Space"])
    calls = _patch_repo_defaults(monkeypatch, canonical_row=canonical)
    monkeypatch.setattr(
        graph_repository,
        "list_lexical_candidates",
        lambda *args, **kwargs: [
            _candidate_row(21, lexical=0.91),
            _candidate_row(22, lexical=0.78),
        ],
    )

    resolved = resolver.resolve_concept(
        workspace_id=1,
        chunk_id=2,
        raw_concept=ExtractedConcept(name="Vector Space", context_snippet="ctx", description=""),
        budgets=ResolverBudgets(max_llm_calls_per_chunk=3, max_llm_calls_per_document=50),
    )

    assert resolved.concept_id == 21
    assert resolved.method == "lexical"
    assert llm.disambiguate_calls == 0
    assert calls["updated"] == []


def test_vector_threshold_merge_when_lexical_ambiguous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Vector signal should merge when lexical margin is too small."""
    llm = StubLLM({"decision": "CREATE_NEW", "confidence": 1.0})
    resolver = _resolver(llm, embedding_provider=StubEmbeddingProvider([0.1, 0.2, 0.3]))
    canonical = _concept_row(31, aliases=["Concept 31", "eigenvector"])
    _patch_repo_defaults(monkeypatch, canonical_row=canonical)
    monkeypatch.setattr(
        graph_repository,
        "list_lexical_candidates",
        lambda *args, **kwargs: [
            _candidate_row(31, lexical=0.86),
            _candidate_row(32, lexical=0.82),
        ],
    )
    monkeypatch.setattr(
        graph_repository,
        "list_vector_candidates",
        lambda *args, **kwargs: [
            _candidate_row(31, vector=0.96),
            _candidate_row(32, vector=0.81),
        ],
    )

    resolved = resolver.resolve_concept(
        workspace_id=1,
        chunk_id=2,
        raw_concept=ExtractedConcept(name="Eigenvector", context_snippet="ctx", description=""),
        budgets=ResolverBudgets(max_llm_calls_per_chunk=3, max_llm_calls_per_document=50),
    )

    assert resolved.concept_id == 31
    assert resolved.method == "vector"
    assert llm.disambiguate_calls == 0


def test_llm_low_confidence_falls_back_to_create(monkeypatch: pytest.MonkeyPatch) -> None:
    """Low-confidence LLM outputs should default to CREATE_NEW."""
    llm = StubLLM({"decision": "MERGE_INTO", "merge_into_id": 40, "confidence": 0.40})
    resolver = _resolver(llm)
    calls = _patch_repo_defaults(monkeypatch)
    monkeypatch.setattr(
        graph_repository,
        "list_lexical_candidates",
        lambda *args, **kwargs: [
            _candidate_row(40, lexical=0.62),
            _candidate_row(41, lexical=0.61),
        ],
    )

    resolved = resolver.resolve_concept(
        workspace_id=1,
        chunk_id=2,
        raw_concept=ExtractedConcept(name="Ambiguous Name", context_snippet="ctx", description=""),
        budgets=ResolverBudgets(max_llm_calls_per_chunk=3, max_llm_calls_per_document=50),
    )

    assert resolved.created is True
    assert llm.disambiguate_calls == 1
    assert calls["upsert_map"][0]["method"] == "llm"


@pytest.mark.parametrize(
    ("max_per_chunk", "max_per_document"),
    [(0, 50), (3, 0)],
)
def test_budget_hard_stop_skips_llm(
    monkeypatch: pytest.MonkeyPatch,
    max_per_chunk: int,
    max_per_document: int,
) -> None:
    """LLM should not run when chunk or document caps are already exhausted."""
    events: list[dict[str, Any]] = []
    set_event_sink(events)
    configure_observability(
        get_settings().model_copy(
            update={
                "observability_enabled": True,
                "observability_otlp_endpoint": None,
                "observability_service_name": "colearni-test",
            }
        )
    )
    llm = StubLLM({"decision": "MERGE_INTO", "merge_into_id": 55, "confidence": 0.9})
    resolver = _resolver(llm)
    _patch_repo_defaults(monkeypatch)
    monkeypatch.setattr(
        graph_repository,
        "list_lexical_candidates",
        lambda *args, **kwargs: [_candidate_row(55, lexical=0.5)],
    )

    resolved = resolver.resolve_concept(
        workspace_id=1,
        chunk_id=2,
        raw_concept=ExtractedConcept(name="Needs LLM", context_snippet="ctx", description=""),
        budgets=ResolverBudgets(
            max_llm_calls_per_chunk=max_per_chunk,
            max_llm_calls_per_document=max_per_document,
        ),
    )

    assert resolved.created is True
    assert llm.disambiguate_calls == 0
    hard_stops = [
        event for event in events if event["event_name"] == "graph.resolver.budget.hard_stop"
    ]
    assert len(hard_stops) == 1
    expected_reason = "chunk_cap_reached" if max_per_chunk == 0 else "document_cap_reached"
    assert hard_stops[0]["reason"] == expected_reason
    set_event_sink(None)


def test_llm_error_falls_back_to_create(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolver should fallback to CREATE_NEW if LLM disambiguation fails."""
    llm = StubLLM(RuntimeError("timeout"))
    resolver = _resolver(llm)
    _patch_repo_defaults(monkeypatch)
    monkeypatch.setattr(
        graph_repository,
        "list_lexical_candidates",
        lambda *args, **kwargs: [_candidate_row(70, lexical=0.51)],
    )

    resolved = resolver.resolve_concept(
        workspace_id=1,
        chunk_id=2,
        raw_concept=ExtractedConcept(name="Timeout Concept", context_snippet="ctx", description=""),
        budgets=ResolverBudgets(max_llm_calls_per_chunk=3, max_llm_calls_per_document=50),
    )

    assert resolved.created is True
    assert llm.disambiguate_calls == 1


def test_upsert_edge_normalizes_keywords_and_weight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Edge upsert should pass deduped keywords and non-negative weight to repository."""
    llm = StubLLM({"decision": "CREATE_NEW", "confidence": 1.0})
    resolver = _resolver(llm)

    captured: dict[str, Any] = {}

    def _capture_edge(*args, **kwargs):  # noqa: ANN001, ANN202
        captured.update(kwargs)
        return 777

    monkeypatch.setattr(graph_repository, "upsert_canonical_edge", _capture_edge)
    monkeypatch.setattr(graph_repository, "insert_provenance", lambda *args, **kwargs: None)

    edge_id = resolver.upsert_edge(
        workspace_id=1,
        chunk_id=2,
        raw_edge=ExtractedEdge(
            src_name="A",
            tgt_name="B",
            relation_type="relates_to",
            description="desc",
            keywords=["span", " Span ", "dimension"],
            weight=-5.0,
        ),
        src_concept_id=101,
        tgt_concept_id=202,
    )

    assert edge_id == 777
    assert captured["keywords"] == ["span", "dimension"]
    assert captured["delta_weight"] == 0.0
