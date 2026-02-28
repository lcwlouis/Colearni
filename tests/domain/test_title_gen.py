"""Unit tests for topic-aware session title generation (S41)."""

from __future__ import annotations

from domain.chat.title_gen import generate_session_title


def test_title_from_concept_name_short() -> None:
    title = generate_session_title(user_query="explain it", concept_name="Eigenvalue")
    assert title == "Eigenvalue Discussion"


def test_title_from_concept_name_multi_word() -> None:
    title = generate_session_title(user_query="what is it", concept_name="Linear Algebra")
    assert title == "Linear Algebra"


def test_title_from_concept_name_long() -> None:
    title = generate_session_title(
        user_query="details",
        concept_name="Multi Word Concept With Many Parts Here",
    )
    assert len(title.split()) <= 5


def test_title_from_query_strips_prefix() -> None:
    title = generate_session_title(user_query="Can you explain photosynthesis?", concept_name=None)
    assert "Photosynthesis" in title
    assert "Can" not in title


def test_title_from_query_removes_punctuation() -> None:
    title = generate_session_title(user_query="What is quantum mechanics?", concept_name=None)
    assert not title.endswith("?")


def test_title_from_short_query() -> None:
    title = generate_session_title(user_query="hi", concept_name=None)
    assert len(title.split()) >= 2


def test_title_is_title_case() -> None:
    title = generate_session_title(user_query="explain the concept of inertia", concept_name=None)
    words = title.split()
    assert all(w[0].isupper() for w in words)


def test_title_max_five_words() -> None:
    title = generate_session_title(
        user_query="I want to understand the deep details of abstract algebra concepts",
        concept_name=None,
    )
    assert len(title.split()) <= 5


def test_concept_name_preferred_over_query() -> None:
    title = generate_session_title(
        user_query="tell me about vectors",
        concept_name="Vector Space",
    )
    assert "Vector" in title
    assert "Space" in title
