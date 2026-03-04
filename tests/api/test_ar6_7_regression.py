"""AR6.7 regression tests for reopened AR2/AR5/AR7 behaviors.

Covers:
- Concept activity API endpoint (AR7.1)
- Graph evidence context format (AR2.7)
- Switch-threshold policy edge cases (AR7.4)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from adapters.db.dependencies import get_db_session
from apps.api.dependencies import WorkspaceContext, get_workspace_context
from apps.api.main import app
from fastapi.testclient import TestClient

from domain.chat.concept_resolver import (
    ConceptInfo,
    _SWITCH_CONFIDENCE_THRESHOLD,
    _to_confidence,
    resolve_concept_for_turn,
)
from domain.retrieval.evidence_planner import _expand_graph_neighbors


# ── Fixtures ──────────────────────────────────────────────────────────

_FAKE_USER = type(
    "FakeUser", (), {"id": 3, "public_id": "u-fake", "email": "t@t.com", "display_name": None}
)()
_FAKE_WS_CTX = WorkspaceContext(workspace_id=2, user=_FAKE_USER)

_ACTIVITY_PAYLOAD = {
    "workspace_id": 2,
    "user_id": 3,
    "concept_id": 42,
    "practice_quizzes": {"count": 0, "average_score": None, "quizzes": []},
    "level_up_quizzes": {"count": 0, "passed_count": 0, "quizzes": []},
    "flashcard_runs": {"count": 0, "total_cards_generated": 0, "runs": []},
    "affordances": {
        "can_generate_flashcards": True,
        "can_create_practice_quiz": True,
        "can_create_level_up_quiz": False,
        "has_prior_flashcards": False,
        "has_prior_practice": False,
        "has_prior_level_up": False,
    },
}


def _override_db() -> Any:
    yield object()


def _override_ws_ctx() -> WorkspaceContext:
    return _FAKE_WS_CTX


# ── API endpoint: concept activity (AR7.1) ────────────────────────────

class TestConceptActivityEndpoint:
    def test_concept_activity_returns_200(self, monkeypatch: Any) -> None:
        """GET /practice/concepts/{id}/activity returns structured response."""
        monkeypatch.setattr(
            "domain.learning.concept_activity.get_concept_activity",
            lambda *a, **kw: _ACTIVITY_PAYLOAD,
        )
        app.dependency_overrides[get_db_session] = _override_db
        app.dependency_overrides[get_workspace_context] = _override_ws_ctx
        try:
            client = TestClient(app)
            resp = client.get("/workspaces/test-ws/practice/concepts/42/activity")
            assert resp.status_code == 200
            body = resp.json()
            assert body["concept_id"] == 42
            assert "practice_quizzes" in body
            assert "level_up_quizzes" in body
            assert "flashcard_runs" in body
            assert "affordances" in body
        finally:
            app.dependency_overrides.pop(get_db_session, None)
            app.dependency_overrides.pop(get_workspace_context, None)

    def test_concept_activity_error_returns_422(self, monkeypatch: Any) -> None:
        """Domain errors are surfaced as 422."""
        def _raise(*a: Any, **kw: Any) -> None:
            raise ValueError("no such concept")

        monkeypatch.setattr(
            "domain.learning.concept_activity.get_concept_activity", _raise,
        )
        app.dependency_overrides[get_db_session] = _override_db
        app.dependency_overrides[get_workspace_context] = _override_ws_ctx
        try:
            client = TestClient(app)
            resp = client.get("/workspaces/test-ws/practice/concepts/999/activity")
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_db_session, None)
            app.dependency_overrides.pop(get_workspace_context, None)


# ── Graph evidence context format (AR2.7) ──────────────────────────────

class TestGraphEvidenceContextFormat:
    def test_expand_graph_neighbors_context_has_structured_lines(self, monkeypatch: Any) -> None:
        """Context string should have one line per neighbor with name and description."""
        fake_subgraph = {
            "nodes": [
                {
                    "concept_id": 5,
                    "canonical_name": "Active Concept",
                    "description": "The currently selected concept",
                },
                {
                    "concept_id": 10,
                    "canonical_name": "Gradient Descent",
                    "description": "An optimization algorithm",
                },
                {
                    "concept_id": 11,
                    "canonical_name": "Loss Function",
                    "description": "Measures prediction error",
                },
            ],
            "edges": [],
        }
        monkeypatch.setattr(
            "domain.graph.explore.get_bounded_subgraph",
            lambda *a, **kw: fake_subgraph,
        )
        session = MagicMock()
        names, context = _expand_graph_neighbors(session, workspace_id=1, concept_id=5, max_hops=1)
        assert len(names) == 2
        assert "Gradient Descent" in names
        assert "Loss Function" in names
        assert "Gradient Descent" in context
        assert "Loss Function" in context
        # Each neighbor should appear on its own line
        lines = [line for line in context.strip().split("\n") if line.strip()]
        assert len(lines) >= 2

    def test_expand_graph_neighbors_empty_returns_empty_context(self, monkeypatch: Any) -> None:
        """No neighbors → empty names list and empty context string."""
        monkeypatch.setattr(
            "domain.graph.explore.get_bounded_subgraph",
            lambda *a, **kw: {"nodes": [], "edges": []},
        )
        session = MagicMock()
        names, context = _expand_graph_neighbors(session, workspace_id=1, concept_id=5, max_hops=1)
        assert names == []
        assert context == ""


# ── Switch threshold edge cases (AR7.4) ──────────────────────────────


class _FakeSession:
    def execute(self, *_: Any, **__: Any) -> Any:
        raise AssertionError("should not be called")


class TestSwitchThresholdEdgeCases:
    def test_boundary_below_threshold_no_switch(self, monkeypatch: Any) -> None:
        """Score that maps to exactly the threshold boundary should NOT switch."""
        concept_a = ConceptInfo(concept_id=1, canonical_name="A")
        concept_b = ConceptInfo(concept_id=2, canonical_name="B")

        monkeypatch.setattr(
            "domain.chat.concept_resolver._concept_by_id",
            lambda _s, workspace_id, concept_id: concept_a if concept_id == 1 else None,
        )
        # score 2.5 → confidence 0.65, below 0.75 threshold
        monkeypatch.setattr(
            "domain.chat.concept_resolver._infer_concept",
            lambda *a, **kw: (concept_b, 2.5),
        )

        r = resolve_concept_for_turn(
            _FakeSession(),
            workspace_id=1,
            query="something",
            history_text="",
            current_concept_id=1,
            suggested_concept_id=None,
            switch_decision=None,
        )
        assert r.resolved_concept is not None
        assert r.resolved_concept.concept_id == 1  # stayed
        assert r.switch_suggestion is None

    def test_boundary_at_threshold_switches(self, monkeypatch: Any) -> None:
        """Score that maps to >= threshold should trigger switch suggestion."""
        concept_a = ConceptInfo(concept_id=1, canonical_name="A")
        concept_b = ConceptInfo(concept_id=2, canonical_name="B")

        monkeypatch.setattr(
            "domain.chat.concept_resolver._concept_by_id",
            lambda _s, workspace_id, concept_id: concept_a if concept_id == 1 else None,
        )
        # score 3.0 → confidence 0.80, above 0.75 threshold
        monkeypatch.setattr(
            "domain.chat.concept_resolver._infer_concept",
            lambda *a, **kw: (concept_b, 3.0),
        )

        r = resolve_concept_for_turn(
            _FakeSession(),
            workspace_id=1,
            query="something specific about B",
            history_text="",
            current_concept_id=1,
            suggested_concept_id=None,
            switch_decision=None,
        )
        assert r.resolved_concept is not None
        assert r.resolved_concept.concept_id == 2  # switched
        assert r.switch_suggestion is not None

    def test_no_current_concept_does_not_trigger_switch(self, monkeypatch: Any) -> None:
        """When there is no current concept, no switch suggestion is created."""
        concept_b = ConceptInfo(concept_id=2, canonical_name="B")

        monkeypatch.setattr(
            "domain.chat.concept_resolver._concept_by_id",
            lambda _s, workspace_id, concept_id: None,
        )
        monkeypatch.setattr(
            "domain.chat.concept_resolver._infer_concept",
            lambda *a, **kw: (concept_b, 5.0),
        )

        r = resolve_concept_for_turn(
            _FakeSession(),
            workspace_id=1,
            query="gradient descent",
            history_text="",
            current_concept_id=None,
            suggested_concept_id=None,
            switch_decision=None,
        )
        assert r.resolved_concept is not None
        assert r.resolved_concept.concept_id == 2
        assert r.switch_suggestion is None

    def test_confidence_mapping_covers_all_score_ranges(self) -> None:
        """Verify _to_confidence produces expected values across score ranges."""
        assert _to_confidence(score=0.0, used_suggestion=False) == 0.4
        assert _to_confidence(score=1.0, used_suggestion=False) == 0.65
        assert _to_confidence(score=3.0, used_suggestion=False) == 0.8
        assert _to_confidence(score=4.0, used_suggestion=False) == 0.95
        assert _to_confidence(score=0.0, used_suggestion=True) == 0.6
