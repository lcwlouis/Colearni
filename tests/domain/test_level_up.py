"""Unit tests for GP8 – topic completion cascading to subtopics."""

from __future__ import annotations

from unittest.mock import patch

from domain.learning.quiz_flow import cascade_mastery_to_children


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MOD = "domain.learning.quiz_flow"


def _make_mastery(status: str, score: float = 0.5):
    return {"status": status, "score": score}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_topic_cascades_mastery_to_subtopics() -> None:
    """Passing a topic-tier concept cascades mastery to its child concepts."""
    upserted: list[tuple[int, str]] = []

    def fake_upsert(session, *, workspace_id, user_id, concept_id, score, status):
        upserted.append((concept_id, status))

    with (
        patch(f"{_MOD}._lookup_concept_tier", return_value="topic"),
        patch(f"{_MOD}._get_child_concept_ids", return_value=[10, 11, 12]),
        patch(f"{_MOD}._lookup_mastery", return_value=None),
        patch(f"{_MOD}._upsert_mastery", side_effect=fake_upsert),
    ):
        cascaded = cascade_mastery_to_children(
            None,  # session stub
            workspace_id=1,
            user_id=2,
            concept_id=100,
            score=0.9,
        )

    assert cascaded == [10, 11, 12]
    assert all(status == "learned" for _, status in upserted)


def test_umbrella_cascades_mastery_to_children() -> None:
    """Umbrella-tier concepts also cascade downward."""
    with (
        patch(f"{_MOD}._lookup_concept_tier", return_value="umbrella"),
        patch(f"{_MOD}._get_child_concept_ids", return_value=[20]),
        patch(f"{_MOD}._lookup_mastery", return_value=None),
        patch(f"{_MOD}._upsert_mastery"),
    ):
        cascaded = cascade_mastery_to_children(
            None, workspace_id=1, user_id=2, concept_id=200, score=0.85,
        )

    assert cascaded == [20]


def test_subtopic_cascades_to_granular() -> None:
    """Subtopic-tier concepts cascade to their granular children."""
    with (
        patch(f"{_MOD}._lookup_concept_tier", return_value="subtopic"),
        patch(f"{_MOD}._get_child_concept_ids", return_value=[30]),
        patch(f"{_MOD}._lookup_mastery", return_value=None),
        patch(f"{_MOD}._upsert_mastery"),
    ):
        cascaded = cascade_mastery_to_children(
            None, workspace_id=1, user_id=2, concept_id=300, score=0.8,
        )

    assert cascaded == [30]


def test_granular_does_not_cascade() -> None:
    """Granular-tier concepts never cascade (no children by definition)."""
    with patch(f"{_MOD}._lookup_concept_tier", return_value="granular"):
        cascaded = cascade_mastery_to_children(
            None, workspace_id=1, user_id=2, concept_id=400, score=0.9,
        )

    assert cascaded == []


def test_no_upward_cascade_from_subtopic_to_topic() -> None:
    """Passing a subtopic does NOT cascade upward to its parent topic.

    The cascade function only looks at *children* (via get_child_concept_ids),
    never parents.  A granular concept has no cascadable tier either.
    """
    with patch(f"{_MOD}._lookup_concept_tier", return_value="granular"):
        cascaded = cascade_mastery_to_children(
            None, workspace_id=1, user_id=2, concept_id=500, score=0.9,
        )

    assert cascaded == []


def test_already_learned_children_are_skipped() -> None:
    """Children already marked 'learned' are not re-upserted."""
    upserted: list[int] = []

    def fake_upsert(session, *, workspace_id, user_id, concept_id, score, status):
        upserted.append(concept_id)

    def fake_lookup_mastery(session, *, workspace_id, user_id, concept_id):
        if concept_id == 11:
            return _make_mastery("learned", 0.95)
        return None

    with (
        patch(f"{_MOD}._lookup_concept_tier", return_value="topic"),
        patch(f"{_MOD}._get_child_concept_ids", return_value=[10, 11, 12]),
        patch(f"{_MOD}._lookup_mastery", side_effect=fake_lookup_mastery),
        patch(f"{_MOD}._upsert_mastery", side_effect=fake_upsert),
    ):
        cascaded = cascade_mastery_to_children(
            None, workspace_id=1, user_id=2, concept_id=100, score=0.9,
        )

    assert cascaded == [10, 12]
    assert 11 not in upserted


def test_no_children_returns_empty() -> None:
    """Concept with cascadable tier but no children returns empty list."""
    with (
        patch(f"{_MOD}._lookup_concept_tier", return_value="topic"),
        patch(f"{_MOD}._get_child_concept_ids", return_value=[]),
    ):
        cascaded = cascade_mastery_to_children(
            None, workspace_id=1, user_id=2, concept_id=100, score=0.9,
        )

    assert cascaded == []


def test_none_tier_does_not_cascade() -> None:
    """Concept with no tier set does not cascade."""
    with patch(f"{_MOD}._lookup_concept_tier", return_value=None):
        cascaded = cascade_mastery_to_children(
            None, workspace_id=1, user_id=2, concept_id=100, score=0.9,
        )

    assert cascaded == []


def test_learning_children_are_upgraded() -> None:
    """Children with status 'learning' are upgraded to 'learned'."""
    upserted: list[tuple[int, str]] = []

    def fake_upsert(session, *, workspace_id, user_id, concept_id, score, status):
        upserted.append((concept_id, status))

    with (
        patch(f"{_MOD}._lookup_concept_tier", return_value="topic"),
        patch(f"{_MOD}._get_child_concept_ids", return_value=[10]),
        patch(f"{_MOD}._lookup_mastery", return_value=_make_mastery("learning", 0.4)),
        patch(f"{_MOD}._upsert_mastery", side_effect=fake_upsert),
    ):
        cascaded = cascade_mastery_to_children(
            None, workspace_id=1, user_id=2, concept_id=100, score=0.9,
        )

    assert cascaded == [10]
    assert upserted == [(10, "learned")]
