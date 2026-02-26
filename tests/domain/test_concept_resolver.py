from __future__ import annotations

from typing import Any

from domain.chat.concept_resolver import (
    ConceptInfo,
    _infer_concept,
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
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def execute(self, *_args: Any, **_kwargs: Any) -> _MappingsResult:
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
