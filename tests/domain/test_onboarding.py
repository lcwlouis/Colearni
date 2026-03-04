"""Tests for onboarding domain (suggest_starting_topics) and API route."""

from __future__ import annotations

from typing import Any

import pytest
from domain.onboarding.status import get_onboarding_status, suggest_starting_topics


class _FakeResult:
    def __init__(self, mappings: list[dict[str, Any]]) -> None:
        self._mappings = mappings
        self._scalar: Any = 0

    def mappings(self) -> "_FakeResult":
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._mappings

    def scalar_one(self) -> Any:
        return self._scalar


class _FakeSession:
    """Minimal session double for onboarding queries."""

    def __init__(
        self,
        *,
        doc_count: int = 0,
        concept_count: int = 0,
        topic_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self._doc_count = doc_count
        self._concept_count = concept_count
        self._topic_rows = topic_rows or []
        self._call_idx = 0

    def execute(self, *args: Any, **kwargs: Any) -> _FakeResult:  # noqa: ARG002
        self._call_idx += 1
        # First call: doc_count, second: concept_count, third: topics
        if self._call_idx == 1:
            r = _FakeResult([])
            r._scalar = self._doc_count
            return r
        if self._call_idx == 2:
            r = _FakeResult([])
            r._scalar = self._concept_count
            return r
        return _FakeResult(self._topic_rows)


def test_suggest_starting_topics_returns_top_by_degree() -> None:
    rows = [
        {"concept_id": 1, "canonical_name": "Linear Map", "description": "Maps vectors.", "tier": "topic", "degree": 5},
        {"concept_id": 2, "canonical_name": "Eigenvalue", "description": None, "tier": None, "degree": 3},
    ]
    # suggest_starting_topics calls execute() once directly — use a simple stub
    class _DirectSession:
        def execute(self, *a: Any, **kw: Any) -> Any:  # noqa: ARG002
            return _FakeResult(rows)

    result = suggest_starting_topics(_DirectSession(), workspace_id=1, limit=5)
    assert len(result) == 2
    assert result[0]["concept_id"] == 1
    assert result[0]["canonical_name"] == "Linear Map"
    assert result[0]["degree"] == 5
    assert result[0]["tier"] == "topic"
    assert result[1]["description"] is None
    assert result[1]["tier"] is None


def test_suggest_starting_topics_empty_workspace() -> None:
    class _EmptySession:
        def execute(self, *a: Any, **kw: Any) -> Any:  # noqa: ARG002
            return _FakeResult([])

    result = suggest_starting_topics(_EmptySession(), workspace_id=1, limit=5)
    assert result == []


def test_get_onboarding_status_no_docs() -> None:
    session = _FakeSession(doc_count=0, concept_count=0)
    status = get_onboarding_status(session, workspace_id=1)
    assert status["has_documents"] is False
    assert status["has_active_concepts"] is False
    assert status["suggested_topics"] == []


def test_get_onboarding_status_with_concepts() -> None:
    topics = [
        {"concept_id": 1, "canonical_name": "Basis", "description": "Foundation.", "tier": "umbrella", "degree": 4},
    ]
    session = _FakeSession(doc_count=2, concept_count=3, topic_rows=topics)
    status = get_onboarding_status(session, workspace_id=1)
    assert status["has_documents"] is True
    assert status["has_active_concepts"] is True
    assert len(status["suggested_topics"]) == 1
    assert status["suggested_topics"][0]["tier"] == "umbrella"


def test_onboarding_route_exists() -> None:
    from apps.api.main import app

    spec = app.openapi()
    assert "/workspaces/{ws_id}/onboarding/status" in spec["paths"]
    assert "get" in spec["paths"]["/workspaces/{ws_id}/onboarding/status"]
