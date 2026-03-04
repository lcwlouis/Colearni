"""Unit tests for SM-2 variant spaced repetition scheduler."""

from __future__ import annotations

from datetime import datetime, timezone

from domain.learning.spaced_repetition import _MIN_INTERVAL_DAYS, compute_next_review


def test_again_halves_interval() -> None:
    new_interval, due = compute_next_review(current_interval_days=4.0, self_rating="again")
    assert new_interval == 2.0
    assert due > datetime.now(tz=timezone.utc)


def test_hard_keeps_interval() -> None:
    new_interval, due = compute_next_review(current_interval_days=3.0, self_rating="hard")
    assert new_interval == 3.0
    assert due > datetime.now(tz=timezone.utc)


def test_good_multiplies_by_2_5() -> None:
    new_interval, due = compute_next_review(current_interval_days=2.0, self_rating="good")
    assert new_interval == 5.0


def test_easy_multiplies_by_4() -> None:
    new_interval, due = compute_next_review(current_interval_days=1.0, self_rating="easy")
    assert new_interval == 4.0


def test_again_respects_minimum_interval() -> None:
    new_interval, _ = compute_next_review(current_interval_days=0.1, self_rating="again")
    assert new_interval == _MIN_INTERVAL_DAYS


def test_initial_interval_again() -> None:
    new_interval, _ = compute_next_review(current_interval_days=1.0, self_rating="again")
    assert new_interval == 0.5


def test_unknown_rating_uses_1x_multiplier() -> None:
    new_interval, _ = compute_next_review(current_interval_days=2.0, self_rating="unknown")
    assert new_interval == 2.0


def test_due_flashcards_route_exists() -> None:
    from apps.api.main import app

    spec = app.openapi()
    assert "/workspaces/{ws_id}/practice/flashcards/due" in spec["paths"]
    assert "get" in spec["paths"]["/workspaces/{ws_id}/practice/flashcards/due"]
