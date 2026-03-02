"""Unit tests for offline graph gardener budgets and merge bookkeeping."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from adapters.db import graph_repository
from core.contracts import GraphLLMClient
from core.observability import configure_observability, set_event_sink
from core.settings import get_settings
from domain.graph import gardener
from domain.graph import orphan_pruner


class StubGardenerLLM(GraphLLMClient):
    """Deterministic LLM stub for gardener cluster decisions."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self._payload = payload
        self.calls = 0

    def extract_raw_graph(self, *, chunk_text: str) -> Mapping[str, Any]:
        return {"concepts": [], "edges": []}

    def disambiguate(
        self,
        *,
        raw_name: str,
        context_snippet: str | None,
        candidates: Sequence[Mapping[str, object]],
    ) -> Mapping[str, Any]:
        self.calls += 1
        return self._payload

    def generate_tutor_text(self, *, prompt: str, prompt_meta=None, system_prompt=None) -> str:
        return prompt
def _concept(
    concept_id: int,
    *,
    name: str,
    aliases: list[str] | None = None,
    embedding: list[float] | None = None,
    active: bool = True,
    dirty: bool = True,
) -> graph_repository.CanonicalConceptRow:
    return graph_repository.CanonicalConceptRow(
        id=concept_id,
        workspace_id=1,
        canonical_name=name,
        description=f"desc {name}",
        aliases=aliases or [name],
        embedding=embedding,
        is_active=active,
        dirty=dirty,
    )


def _candidate(
    concept_id: int,
    *,
    name: str,
    lexical: float,
) -> graph_repository.CanonicalCandidateRow:
    return graph_repository.CanonicalCandidateRow(
        id=concept_id,
        canonical_name=name,
        description=f"desc {name}",
        aliases=[name],
        lexical_similarity=lexical,
        vector_similarity=None,
    )


def _patch_enrichment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub out provenance, mastery, and neighbor queries used by the gardener."""
    monkeypatch.setattr(
        gardener,
        "count_provenance_for_concepts",
        lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(
        gardener,
        "get_mastered_concept_ids",
        lambda *args, **kwargs: set(),
    )
    monkeypatch.setattr(
        graph_repository,
        "list_neighbor_names",
        lambda *args, **kwargs: [],
    )


def test_gardener_stops_when_llm_budget_is_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero LLM budget should hard-stop before any cluster decision call."""
    _patch_enrichment(monkeypatch)
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
    seed_a = _concept(11, name="Vector Space")
    seed_b = _concept(12, name="Vector Spaces")
    llm = StubGardenerLLM({"decision": "MERGE_INTO", "merge_into_id": 11, "confidence": 0.9})

    monkeypatch.setattr(
        graph_repository,
        "list_null_tier_concepts",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        graph_repository,
        "list_gardener_seed_concepts",
        lambda *args, **kwargs: [seed_a, seed_b],
    )
    monkeypatch.setattr(
        graph_repository,
        "list_lexical_candidates",
        lambda *args, **kwargs: [
            _candidate(11, name="Vector Space", lexical=1.0),
            _candidate(12, name="Vector Spaces", lexical=0.91),
        ],
    )
    monkeypatch.setattr(graph_repository, "list_vector_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        graph_repository,
        "set_canonical_concept_dirty",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        orphan_pruner,
        "prune_orphan_graph_nodes",
        lambda *args, **kwargs: {"pruned_concepts": 0, "pruned_edges": 0},
    )
    monkeypatch.setattr(
        gardener,
        "prune_orphan_graph_nodes",
        lambda *args, **kwargs: {"pruned_concepts": 0, "pruned_edges": 0},
    )

    settings = get_settings().model_copy(
        update={
            "gardener_max_llm_calls_per_run": 0,
            "gardener_max_clusters_per_run": 50,
            "gardener_max_dirty_nodes_per_run": 200,
            "gardener_recent_window_days": 7,
        }
    )
    result = gardener.run_graph_gardener(
        object(),  # type: ignore[arg-type]
        workspace_id=1,
        llm_client=llm,
        settings=settings,
    )

    assert result.stopped_by_llm_budget is True
    assert result.clusters_processed == 0
    assert result.llm_calls == 0
    assert result.merges_applied == 0
    assert llm.calls == 0
    hard_stops = [
        event for event in events if event["event_name"] == "graph.gardener.budget.hard_stop"
    ]
    assert len(hard_stops) == 1
    assert hard_stops[0]["reason"] == "llm_budget_exhausted"
    usage = [event for event in events if event["event_name"] == "graph.gardener.budget.usage"]
    assert usage
    set_event_sink(None)


def test_gardener_stops_when_cluster_budget_is_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cluster cap should stop processing after the first eligible cluster."""
    _patch_enrichment(monkeypatch)
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
    seeds = [
        _concept(11, name="A"),
        _concept(12, name="A-prime"),
        _concept(21, name="B"),
        _concept(22, name="B-prime"),
    ]
    llm = StubGardenerLLM({"decision": "MERGE_INTO", "merge_into_id": 11, "confidence": 0.9})
    merge_calls: list[dict[str, Any]] = []

    monkeypatch.setattr(
        graph_repository,
        "list_null_tier_concepts",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        graph_repository,
        "list_gardener_seed_concepts",
        lambda *args, **kwargs: seeds,
    )

    def _lexical(*args, **kwargs):  # noqa: ANN001, ANN202
        alias = kwargs["alias"]
        if alias == "a":
            return [
                _candidate(11, name="A", lexical=1.0),
                _candidate(12, name="A-prime", lexical=0.93),
            ]
        if alias == "a-prime":
            return [
                _candidate(12, name="A-prime", lexical=1.0),
                _candidate(11, name="A", lexical=0.93),
            ]
        if alias == "b":
            return [
                _candidate(21, name="B", lexical=1.0),
                _candidate(22, name="B-prime", lexical=0.93),
            ]
        return [
            _candidate(22, name="B-prime", lexical=1.0),
            _candidate(21, name="B", lexical=0.93),
        ]

    monkeypatch.setattr(graph_repository, "list_lexical_candidates", _lexical)
    monkeypatch.setattr(graph_repository, "list_vector_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        graph_repository,
        "set_canonical_concept_dirty",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        orphan_pruner,
        "prune_orphan_graph_nodes",
        lambda *args, **kwargs: {"pruned_concepts": 0, "pruned_edges": 0},
    )
    monkeypatch.setattr(
        gardener,
        "prune_orphan_graph_nodes",
        lambda *args, **kwargs: {"pruned_concepts": 0, "pruned_edges": 0},
    )

    def _record_merge(*args, **kwargs):  # noqa: ANN001, ANN202
        merge_calls.append(kwargs)
        return True

    monkeypatch.setattr(gardener, "_execute_merge", _record_merge)

    settings = get_settings().model_copy(
        update={
            "gardener_max_clusters_per_run": 1,
            "gardener_max_llm_calls_per_run": 30,
            "gardener_max_dirty_nodes_per_run": 200,
            "gardener_recent_window_days": 7,
        }
    )
    result = gardener.run_graph_gardener(
        object(),  # type: ignore[arg-type]
        workspace_id=1,
        llm_client=llm,
        settings=settings,
    )

    assert result.clusters_processed == 1
    assert result.stopped_by_cluster_budget is True
    assert result.llm_calls == 1
    assert len(merge_calls) == 1
    hard_stops = [
        event for event in events if event["event_name"] == "graph.gardener.budget.hard_stop"
    ]
    assert len(hard_stops) == 1
    assert hard_stops[0]["reason"] == "cluster_budget_exhausted"
    usage = [event for event in events if event["event_name"] == "graph.gardener.budget.usage"]
    assert usage
    set_event_sink(None)


def test_execute_merge_is_idempotent_when_source_is_already_inactive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Second merge execution should no-op when source has already been deactivated."""
    state = {
        101: _concept(101, name="Vector Space", aliases=["Vector Space", "VS"], active=True),
        102: _concept(102, name="Vector Spaces", aliases=["Vector Spaces"], active=True),
    }
    counters = {"log": 0, "edges": 0, "alias_repoint": 0, "alias_upsert": 0, "deactivate": 0}

    monkeypatch.setattr(
        graph_repository,
        "get_canonical_concept",
        lambda *args, **kwargs: state.get(kwargs["concept_id"]),
    )

    def _log(*args, **kwargs):  # noqa: ANN001, ANN202
        counters["log"] += 1
        return True

    monkeypatch.setattr(graph_repository, "insert_concept_merge_log_idempotent", _log)
    monkeypatch.setattr(
        graph_repository,
        "repoint_edges_for_merge",
        lambda *args, **kwargs: counters.__setitem__("edges", counters["edges"] + 1),
    )
    monkeypatch.setattr(
        graph_repository,
        "repoint_alias_map",
        lambda *args, **kwargs: counters.__setitem__(
            "alias_repoint",
            counters["alias_repoint"] + 1,
        ),
    )
    monkeypatch.setattr(
        graph_repository,
        "ensure_aliases_map_to_concept",
        lambda *args, **kwargs: counters.__setitem__("alias_upsert", counters["alias_upsert"] + 1),
    )

    def _deactivate(*args, **kwargs):  # noqa: ANN001, ANN202
        counters["deactivate"] += 1
        source = state[kwargs["concept_id"]]
        state[kwargs["concept_id"]] = _concept(
            source.id,
            name=source.canonical_name,
            aliases=list(source.aliases),
            active=False,
        )
        return True

    monkeypatch.setattr(graph_repository, "deactivate_canonical_concept", _deactivate)
    monkeypatch.setattr(
        graph_repository,
        "set_canonical_concept_dirty",
        lambda *args, **kwargs: None,
    )

    first = gardener._execute_merge(
        session=object(),  # type: ignore[arg-type]
        workspace_id=1,
        from_concept_id=101,
        to_concept_id=102,
        confidence=0.9,
        method="llm",
        reason="test",
        edge_weight_cap=10.0,
        edge_description_max_chars=300,
    )
    second = gardener._execute_merge(
        session=object(),  # type: ignore[arg-type]
        workspace_id=1,
        from_concept_id=101,
        to_concept_id=102,
        confidence=0.9,
        method="llm",
        reason="test",
        edge_weight_cap=10.0,
        edge_description_max_chars=300,
    )

    assert first is True
    assert second is False
    assert counters == {
        "log": 1,
        "edges": 1,
        "alias_repoint": 1,
        "alias_upsert": 1,
        "deactivate": 1,
    }


def test_execute_merge_runs_required_bookkeeping(monkeypatch: pytest.MonkeyPatch) -> None:
    """Merge execution should perform log/edge/alias/deactivate steps."""
    source = _concept(301, name="S")
    target = _concept(302, name="T")
    calls: list[str] = []

    monkeypatch.setattr(
        graph_repository,
        "get_canonical_concept",
        lambda *args, **kwargs: source if kwargs["concept_id"] == 301 else target,
    )
    monkeypatch.setattr(
        graph_repository,
        "insert_concept_merge_log_idempotent",
        lambda *args, **kwargs: calls.append("merge_log") or True,
    )
    monkeypatch.setattr(
        graph_repository,
        "repoint_edges_for_merge",
        lambda *args, **kwargs: calls.append("edges") or 1,
    )
    monkeypatch.setattr(
        graph_repository,
        "repoint_alias_map",
        lambda *args, **kwargs: calls.append("alias_repoint") or 1,
    )
    monkeypatch.setattr(
        graph_repository,
        "ensure_aliases_map_to_concept",
        lambda *args, **kwargs: calls.append("alias_upsert") or 1,
    )
    monkeypatch.setattr(
        graph_repository,
        "deactivate_canonical_concept",
        lambda *args, **kwargs: calls.append("deactivate") or True,
    )
    monkeypatch.setattr(
        graph_repository,
        "set_canonical_concept_dirty",
        lambda *args, **kwargs: calls.append("set_dirty"),
    )

    changed = gardener._execute_merge(
        session=object(),  # type: ignore[arg-type]
        workspace_id=1,
        from_concept_id=301,
        to_concept_id=302,
        confidence=0.9,
        method="llm",
        reason="test",
        edge_weight_cap=10.0,
        edge_description_max_chars=300,
    )

    assert changed is True
    assert calls == [
        "merge_log",
        "edges",
        "alias_repoint",
        "alias_upsert",
        "deactivate",
        "set_dirty",
    ]


class TierInferenceLLM(StubGardenerLLM):
    """LLM stub that returns a tier string from generate_tutor_text."""

    def __init__(self, tier_response: str = "topic") -> None:
        super().__init__({"decision": "CREATE_NEW", "confidence": 1.0})
        self._tier_response = tier_response

    def generate_tutor_text(self, *, prompt: str, prompt_meta: Any = None, system_prompt: str | None = None) -> str:
        self.calls += 1
        return self._tier_response


def test_gardener_backfills_null_tier_concepts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gardener run should backfill NULL-tier concepts before clustering."""
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
    null_tier_concept = _concept(99, name="Reading a sector")
    llm = TierInferenceLLM(tier_response="granular")
    tier_updates: list[dict[str, Any]] = []

    class MockSession:
        def execute(self, stmt: Any, params: Any = None) -> Any:
            tier_updates.append(params)

    monkeypatch.setattr(
        graph_repository,
        "list_null_tier_concepts",
        lambda *args, **kwargs: [null_tier_concept],
    )
    monkeypatch.setattr(
        graph_repository,
        "list_neighbor_names",
        lambda *args, **kwargs: ["Disk I/O", "File System"],
    )
    monkeypatch.setattr(
        graph_repository,
        "list_gardener_seed_concepts",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        gardener,
        "prune_orphan_graph_nodes",
        lambda *args, **kwargs: {"pruned_concepts": 0, "pruned_edges": 0},
    )

    settings = get_settings().model_copy(
        update={
            "gardener_max_llm_calls_per_run": 10,
            "gardener_max_clusters_per_run": 10,
            "gardener_max_dirty_nodes_per_run": 50,
            "gardener_recent_window_days": 7,
        }
    )
    result = gardener.run_graph_gardener(
        MockSession(),  # type: ignore[arg-type]
        workspace_id=1,
        llm_client=llm,
        settings=settings,
    )

    assert result.tiers_backfilled == 1
    assert result.llm_calls == 1
    assert len(tier_updates) == 1
    assert tier_updates[0]["tier"] == "granular"
    assert tier_updates[0]["concept_id"] == 99
    backfill_events = [
        e for e in events if e["event_name"] == "graph.gardener.tier_backfill"
    ]
    assert len(backfill_events) == 1
    assert backfill_events[0]["inferred_tier"] == "granular"
    set_event_sink(None)


def test_gardener_backfill_respects_llm_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tier backfill should stop when the LLM budget is exhausted."""
    set_event_sink([])
    configure_observability(
        get_settings().model_copy(
            update={
                "observability_enabled": True,
                "observability_otlp_endpoint": None,
                "observability_service_name": "colearni-test",
            }
        )
    )
    concepts_with_no_tier = [
        _concept(i, name=f"Concept {i}") for i in range(1, 6)
    ]
    llm = TierInferenceLLM(tier_response="subtopic")

    class MockSession:
        def execute(self, stmt: Any, params: Any = None) -> Any:
            pass

    monkeypatch.setattr(
        graph_repository,
        "list_null_tier_concepts",
        lambda *args, **kwargs: concepts_with_no_tier,
    )
    monkeypatch.setattr(
        graph_repository,
        "list_neighbor_names",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        graph_repository,
        "list_gardener_seed_concepts",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        gardener,
        "prune_orphan_graph_nodes",
        lambda *args, **kwargs: {"pruned_concepts": 0, "pruned_edges": 0},
    )

    settings = get_settings().model_copy(
        update={
            "gardener_max_llm_calls_per_run": 2,
            "gardener_max_clusters_per_run": 10,
            "gardener_max_dirty_nodes_per_run": 50,
            "gardener_recent_window_days": 7,
        }
    )
    result = gardener.run_graph_gardener(
        MockSession(),  # type: ignore[arg-type]
        workspace_id=1,
        llm_client=llm,
        settings=settings,
    )

    # Only 2 out of 5 should be backfilled due to budget
    assert result.tiers_backfilled == 2
    assert result.llm_calls == 2
    set_event_sink(None)
