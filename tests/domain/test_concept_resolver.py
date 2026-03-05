from __future__ import annotations

from typing import Any

from domain.chat.concept_resolver import (
    ConceptInfo,
    _infer_concept,
    _SWITCH_CONFIDENCE_THRESHOLD,
    resolve_concept_for_turn,
)


class _MappingsResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> _MappingsResult:
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class _SessionWithConceptRows:
    """Fake session that returns concept rows, optionally filtering by tier.

    When the executed SQL contains a tier filter clause, rows are filtered to
    match the same semantics: only rows with tier in ('topic', 'umbrella') or
    tier IS NULL are returned.  This mirrors what the real database would do.
    """

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def execute(self, stmt: Any, *_args: Any, **_kwargs: Any) -> _MappingsResult:
        query_text = str(stmt) if stmt is not None else ""
        if "tier IN" in query_text:
            filtered = [
                r for r in self._rows
                if r.get("tier") in ("topic", "umbrella", None)
            ]
            return _MappingsResult(filtered)
        return _MappingsResult(self._rows)


def test_infer_concept_prioritizes_latest_query_over_history() -> None:
    session = _SessionWithConceptRows(
        [
            {
                "concept_id": 1,
                "canonical_name": "Linear Map",
                "aliases": ["linear transformation"],
            },
            {
                "concept_id": 2,
                "canonical_name": "Gradient Descent",
                "aliases": ["gd"],
            },
        ]
    )
    inferred, score = _infer_concept(
        session,
        workspace_id=1,
        query="Can you explain gradient descent?",
        history_text="Earlier we discussed linear maps and linear transformations.",
        suggested_concept=None,
    )
    assert inferred is not None
    assert inferred.concept_id == 2
    assert score > 0


class _SessionWithExecute:
    def execute(self, *_args: Any, **_kwargs: Any) -> Any:  # pragma: no cover - monkeypatched
        raise AssertionError("not expected")


def test_resolve_concept_emits_switch_suggestion(monkeypatch: Any) -> None:
    concept_current = ConceptInfo(concept_id=1, canonical_name="Linear Map")
    concept_next = ConceptInfo(concept_id=2, canonical_name="Gradient Descent")

    def fake_by_id(
        _session: Any,
        *,
        workspace_id: int,
        concept_id: int | None,
    ) -> ConceptInfo | None:
        _ = workspace_id
        if concept_id == 1:
            return concept_current
        if concept_id == 2:
            return concept_next
        return None

    monkeypatch.setattr("domain.chat.concept_resolver._concept_by_id", fake_by_id)
    monkeypatch.setattr(
        "domain.chat.concept_resolver._infer_concept",
        lambda *args, **kwargs: (concept_next, 4.0),
    )

    resolution = resolve_concept_for_turn(
        _SessionWithExecute(),
        workspace_id=1,
        query="How does gradient descent work?",
        history_text="linear map",
        current_concept_id=1,
        suggested_concept_id=None,
        switch_decision=None,
    )
    assert resolution.resolved_concept is not None
    assert resolution.resolved_concept.concept_id == 2
    assert resolution.switch_suggestion is not None
    assert resolution.switch_suggestion.from_concept_id == 1
    assert resolution.switch_suggestion.to_concept_id == 2


def test_weak_mismatch_stays_on_current_concept(monkeypatch: Any) -> None:
    """A partial token overlap (confidence < threshold) should NOT trigger a switch."""
    concept_current = ConceptInfo(concept_id=1, canonical_name="Linear Map")
    concept_next = ConceptInfo(concept_id=2, canonical_name="Gradient Descent")

    def fake_by_id(
        _session: Any,
        *,
        workspace_id: int,
        concept_id: int | None,
    ) -> ConceptInfo | None:
        _ = workspace_id
        if concept_id == 1:
            return concept_current
        if concept_id == 2:
            return concept_next
        return None

    monkeypatch.setattr("domain.chat.concept_resolver._concept_by_id", fake_by_id)
    # score=2.0 → confidence 0.65, below threshold
    monkeypatch.setattr(
        "domain.chat.concept_resolver._infer_concept",
        lambda *args, **kwargs: (concept_next, 2.0),
    )

    resolution = resolve_concept_for_turn(
        _SessionWithExecute(),
        workspace_id=1,
        query="Something about gradients maybe",
        history_text="linear map",
        current_concept_id=1,
        suggested_concept_id=None,
        switch_decision=None,
    )
    # Should stay on current concept
    assert resolution.resolved_concept is not None
    assert resolution.resolved_concept.concept_id == 1
    assert resolution.switch_suggestion is None


def test_strong_mismatch_suggests_switch(monkeypatch: Any) -> None:
    """An exact match (confidence >= threshold) should create a switch suggestion."""
    concept_current = ConceptInfo(concept_id=1, canonical_name="Linear Map")
    concept_next = ConceptInfo(concept_id=2, canonical_name="Gradient Descent")

    def fake_by_id(
        _session: Any,
        *,
        workspace_id: int,
        concept_id: int | None,
    ) -> ConceptInfo | None:
        _ = workspace_id
        if concept_id == 1:
            return concept_current
        if concept_id == 2:
            return concept_next
        return None

    monkeypatch.setattr("domain.chat.concept_resolver._concept_by_id", fake_by_id)
    # score=3.0 → confidence 0.8, above threshold
    monkeypatch.setattr(
        "domain.chat.concept_resolver._infer_concept",
        lambda *args, **kwargs: (concept_next, 3.0),
    )

    resolution = resolve_concept_for_turn(
        _SessionWithExecute(),
        workspace_id=1,
        query="Explain gradient descent in detail",
        history_text="linear map",
        current_concept_id=1,
        suggested_concept_id=None,
        switch_decision=None,
    )
    assert resolution.resolved_concept is not None
    assert resolution.resolved_concept.concept_id == 2
    assert resolution.switch_suggestion is not None
    assert resolution.switch_suggestion.to_concept_id == 2


def test_switch_threshold_is_reasonable() -> None:
    """Threshold should be between 0.5 and 0.95 to avoid too-eager or too-strict policy."""
    assert 0.5 < _SWITCH_CONFIDENCE_THRESHOLD < 0.95


def test_infer_concept_excludes_subtopic_and_granular_tiers() -> None:
    """Only topic, umbrella, and NULL-tier concepts should be switch candidates."""
    rows = [
        {"concept_id": 1, "canonical_name": "Machine Learning", "aliases": [], "tier": "umbrella"},
        {"concept_id": 2, "canonical_name": "Gradient Descent", "aliases": [], "tier": "topic"},
        {"concept_id": 3, "canonical_name": "Learning Rate", "aliases": [], "tier": "subtopic"},
        {"concept_id": 4, "canonical_name": "Adam Optimizer", "aliases": [], "tier": "granular"},
        {"concept_id": 5, "canonical_name": "Neural Networks", "aliases": [], "tier": None},
    ]
    session = _SessionWithConceptRows(rows)

    # Query explicitly mentions "Learning Rate" (subtopic) — it must NOT be inferred
    inferred, score = _infer_concept(
        session,
        workspace_id=1,
        query="Tell me about Learning Rate",
        history_text="",
        suggested_concept=None,
    )
    # The subtopic "Learning Rate" should be excluded; best match should be a
    # topic/umbrella/NULL concept instead.
    assert inferred is not None
    assert inferred.concept_id not in (3, 4), (
        f"subtopic/granular concept {inferred.concept_id} should not be a switch candidate"
    )


def test_infer_concept_returns_topic_and_umbrella_tiers() -> None:
    """Topic and umbrella concepts should be valid switch candidates."""
    rows = [
        {"concept_id": 1, "canonical_name": "Gradient Descent", "aliases": ["gd"], "tier": "topic"},
        {"concept_id": 2, "canonical_name": "Learning Rate", "aliases": [], "tier": "subtopic"},
    ]
    session = _SessionWithConceptRows(rows)

    inferred, score = _infer_concept(
        session,
        workspace_id=1,
        query="How does gradient descent work?",
        history_text="",
        suggested_concept=None,
    )
    assert inferred is not None
    assert inferred.concept_id == 1
    assert inferred.tier == "topic"
    assert score > 0


def test_session_scope_blocks_out_of_subtree_resolution(monkeypatch: Any) -> None:
    """When session_concept_id is set, inferred concepts outside the subtree are blocked."""
    concept_root = ConceptInfo(concept_id=10, canonical_name="Machine Learning", tier="topic")
    concept_child = ConceptInfo(concept_id=11, canonical_name="Gradient Descent", tier="subtopic")
    concept_outside = ConceptInfo(concept_id=20, canonical_name="Calculus", tier="topic")

    def fake_by_id(
        _session: Any, *, workspace_id: int, concept_id: int | None,
    ) -> ConceptInfo | None:
        return {10: concept_root, 11: concept_child, 20: concept_outside}.get(concept_id)  # type: ignore[arg-type]

    def fake_subtree(
        _session: Any, *, workspace_id: int, root_concept_id: int,
    ) -> set[int]:
        return {10, 11}

    monkeypatch.setattr("domain.chat.concept_resolver._concept_by_id", fake_by_id)
    monkeypatch.setattr("domain.chat.concept_resolver._get_subtree_concept_ids", fake_subtree)
    # Infer an out-of-scope concept with high confidence
    monkeypatch.setattr(
        "domain.chat.concept_resolver._infer_concept",
        lambda *a, **kw: (concept_outside, 5.0),
    )

    resolution = resolve_concept_for_turn(
        _SessionWithExecute(),
        workspace_id=1,
        query="Tell me about calculus",
        history_text="",
        current_concept_id=11,
        suggested_concept_id=None,
        switch_decision=None,
        session_concept_id=10,
    )
    # Should stay on current (in-subtree) concept, not switch to Calculus
    assert resolution.resolved_concept is not None
    assert resolution.resolved_concept.concept_id == 11
    # Should suggest starting a new chat
    assert resolution.switch_suggestion is not None
    assert "new chat" in resolution.switch_suggestion.reason.lower()
    assert resolution.switch_suggestion.to_concept_id == 20


def test_session_scope_allows_in_subtree_resolution(monkeypatch: Any) -> None:
    """When session_concept_id is set, in-subtree concepts resolve normally."""
    concept_root = ConceptInfo(concept_id=10, canonical_name="Machine Learning", tier="topic")
    concept_child = ConceptInfo(concept_id=11, canonical_name="Gradient Descent", tier="subtopic")

    def fake_by_id(
        _session: Any, *, workspace_id: int, concept_id: int | None,
    ) -> ConceptInfo | None:
        return {10: concept_root, 11: concept_child}.get(concept_id)  # type: ignore[arg-type]

    def fake_subtree(
        _session: Any, *, workspace_id: int, root_concept_id: int,
    ) -> set[int]:
        return {10, 11}

    monkeypatch.setattr("domain.chat.concept_resolver._concept_by_id", fake_by_id)
    monkeypatch.setattr("domain.chat.concept_resolver._get_subtree_concept_ids", fake_subtree)
    monkeypatch.setattr(
        "domain.chat.concept_resolver._infer_concept",
        lambda *a, **kw: (concept_child, 5.0),
    )

    resolution = resolve_concept_for_turn(
        _SessionWithExecute(),
        workspace_id=1,
        query="How does gradient descent work?",
        history_text="",
        current_concept_id=10,
        suggested_concept_id=None,
        switch_decision=None,
        session_concept_id=10,
    )
    assert resolution.resolved_concept is not None
    assert resolution.resolved_concept.concept_id == 11


def test_session_scope_none_behaves_normally(monkeypatch: Any) -> None:
    """When session_concept_id is None, resolver works as before (no scoping)."""
    concept_a = ConceptInfo(concept_id=1, canonical_name="Linear Map")
    concept_b = ConceptInfo(concept_id=2, canonical_name="Gradient Descent")

    def fake_by_id(
        _session: Any, *, workspace_id: int, concept_id: int | None,
    ) -> ConceptInfo | None:
        return {1: concept_a, 2: concept_b}.get(concept_id)  # type: ignore[arg-type]

    monkeypatch.setattr("domain.chat.concept_resolver._concept_by_id", fake_by_id)
    monkeypatch.setattr(
        "domain.chat.concept_resolver._infer_concept",
        lambda *a, **kw: (concept_b, 5.0),
    )

    resolution = resolve_concept_for_turn(
        _SessionWithExecute(),
        workspace_id=1,
        query="Tell me about gradient descent",
        history_text="linear map",
        current_concept_id=1,
        suggested_concept_id=None,
        switch_decision=None,
        session_concept_id=None,
    )
    # Without scoping, should switch freely
    assert resolution.resolved_concept is not None
    assert resolution.resolved_concept.concept_id == 2


def test_session_scope_falls_back_to_root_when_current_outside(monkeypatch: Any) -> None:
    """When current concept is also outside subtree, falls back to session root."""
    concept_root = ConceptInfo(concept_id=10, canonical_name="Machine Learning", tier="topic")
    concept_outside_a = ConceptInfo(concept_id=20, canonical_name="Calculus", tier="topic")
    concept_outside_b = ConceptInfo(concept_id=30, canonical_name="Physics", tier="topic")

    def fake_by_id(
        _session: Any, *, workspace_id: int, concept_id: int | None,
    ) -> ConceptInfo | None:
        return {10: concept_root, 20: concept_outside_a, 30: concept_outside_b}.get(concept_id)  # type: ignore[arg-type]

    def fake_subtree(
        _session: Any, *, workspace_id: int, root_concept_id: int,
    ) -> set[int]:
        return {10, 11}

    monkeypatch.setattr("domain.chat.concept_resolver._concept_by_id", fake_by_id)
    monkeypatch.setattr("domain.chat.concept_resolver._get_subtree_concept_ids", fake_subtree)
    monkeypatch.setattr(
        "domain.chat.concept_resolver._infer_concept",
        lambda *a, **kw: (concept_outside_b, 5.0),
    )

    resolution = resolve_concept_for_turn(
        _SessionWithExecute(),
        workspace_id=1,
        query="Tell me about physics",
        history_text="",
        current_concept_id=20,
        suggested_concept_id=None,
        switch_decision=None,
        session_concept_id=10,
    )
    # Should fall back to session root
    assert resolution.resolved_concept is not None
    assert resolution.resolved_concept.concept_id == 10


def test_infer_concept_allows_null_tier_legacy_concepts() -> None:
    """Legacy concepts with tier=NULL should still be valid switch candidates."""
    rows = [
        {"concept_id": 1, "canonical_name": "Calculus", "aliases": [], "tier": None},
        {"concept_id": 2, "canonical_name": "Calculus Basics", "aliases": [], "tier": "subtopic"},
    ]
    session = _SessionWithConceptRows(rows)

    inferred, score = _infer_concept(
        session,
        workspace_id=1,
        query="Tell me about Calculus",
        history_text="",
        suggested_concept=None,
    )
    assert inferred is not None
    assert inferred.concept_id == 1
    assert inferred.tier is None
    assert score > 0
