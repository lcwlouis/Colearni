"""Unit tests for load_chat_context_for_quiz (S41 quiz history context)."""

from __future__ import annotations

from unittest.mock import patch

from domain.chat.session_memory import load_chat_context_for_quiz


def _make_messages(pairs: list[tuple[str, str]]) -> list[dict]:
    """Create mock chat messages from (role, text) pairs."""
    msgs = []
    for role, text in pairs:
        msgs.append({"type": role, "payload": {"text": text}})
    return msgs


class _FakeSession:
    """Minimal stub for Session (not used by the function under test)."""
    pass


def test_returns_empty_when_no_session_id() -> None:
    result = load_chat_context_for_quiz(_FakeSession(), session_id=None)
    assert result == ""


@patch("domain.chat.session_memory.list_recent_chat_messages")
def test_returns_empty_when_no_messages(mock_list):
    mock_list.return_value = []
    result = load_chat_context_for_quiz(_FakeSession(), session_id=1)
    assert result == ""


@patch("domain.chat.session_memory.list_recent_chat_messages")
def test_formats_user_and_assistant_messages(mock_list):
    mock_list.return_value = _make_messages([
        ("user", "What is gradient descent?"),
        ("assistant", "Gradient descent is an optimization algorithm."),
    ])
    result = load_chat_context_for_quiz(_FakeSession(), session_id=1)
    assert "Learner: What is gradient descent?" in result
    assert "Tutor: Gradient descent is an optimization algorithm." in result


@patch("domain.chat.session_memory.list_recent_chat_messages")
def test_respects_max_turns(mock_list):
    pairs = [(role, f"msg {i}") for i, role in enumerate(["user", "assistant"] * 10)]
    mock_list.return_value = _make_messages(pairs)
    result = load_chat_context_for_quiz(_FakeSession(), session_id=1, max_turns=4)
    lines = [l for l in result.splitlines() if l.strip()]
    assert len(lines) == 4


@patch("domain.chat.session_memory.list_recent_chat_messages")
def test_truncates_long_messages(mock_list):
    long_text = "x" * 500
    mock_list.return_value = _make_messages([("user", long_text)])
    result = load_chat_context_for_quiz(_FakeSession(), session_id=1)
    # Should truncate to 200 chars in the line
    assert len(result.split("Learner: ")[1]) <= 200


@patch("domain.chat.session_memory.list_recent_chat_messages")
def test_skips_system_and_card_messages(mock_list):
    mock_list.return_value = [
        {"type": "system", "payload": {"summary": "compacted context"}},
        {"type": "card", "payload": {"card_type": "quiz_result"}},
        {"type": "user", "payload": {"text": "hello"}},
    ]
    result = load_chat_context_for_quiz(_FakeSession(), session_id=1)
    assert "Learner: hello" in result
    assert "system" not in result.lower()
    assert "card" not in result.lower()


@patch("domain.chat.session_memory.list_recent_chat_messages")
def test_skips_empty_payloads(mock_list):
    mock_list.return_value = [
        {"type": "user", "payload": {"text": ""}},
        {"type": "assistant", "payload": {}},
        {"type": "user", "payload": {"text": "real question"}},
    ]
    result = load_chat_context_for_quiz(_FakeSession(), session_id=1)
    assert "Learner: real question" in result
    lines = [l for l in result.splitlines() if l.strip()]
    assert len(lines) == 1
