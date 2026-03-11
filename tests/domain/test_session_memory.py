"""Unit tests for session_memory – load_history_turns()."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from domain.chat.session_memory import load_history_turns


def _msg(role: str, text: str) -> dict:
    return {"type": role, "payload": {"text": text}}


class TestLoadHistoryTurns:
    """Tests for load_history_turns()."""

    def test_none_session_id_returns_empty(self) -> None:
        session = MagicMock()
        summary, turns = load_history_turns(session, session_id=None)
        assert summary == ""
        assert turns == []

    @patch("domain.chat.session_memory.list_recent_chat_messages", return_value=[])
    @patch("domain.chat.session_memory.latest_system_summary", return_value=None)
    def test_empty_history(self, _sum: MagicMock, _msgs: MagicMock) -> None:
        session = MagicMock()
        summary, turns = load_history_turns(session, session_id=1)
        assert summary == ""
        assert turns == []

    @patch("domain.chat.session_memory.list_recent_chat_messages")
    @patch("domain.chat.session_memory.latest_system_summary", return_value="Prior context")
    def test_paired_turns(self, _sum: MagicMock, mock_msgs: MagicMock) -> None:
        mock_msgs.return_value = [
            _msg("user", "What is DNA?"),
            _msg("assistant", "DNA is a molecule."),
            _msg("user", "Tell me more"),
            _msg("assistant", "It has a double helix."),
        ]
        session = MagicMock()
        summary, turns = load_history_turns(session, session_id=1)
        assert summary == "Prior context"
        assert turns == [
            ("What is DNA?", "DNA is a molecule."),
            ("Tell me more", "It has a double helix."),
        ]

    @patch("domain.chat.session_memory.list_recent_chat_messages")
    @patch("domain.chat.session_memory.latest_system_summary", return_value="")
    def test_unpaired_user_message(self, _sum: MagicMock, mock_msgs: MagicMock) -> None:
        """A trailing user message with no assistant reply yet."""
        mock_msgs.return_value = [
            _msg("user", "What is RNA?"),
            _msg("assistant", "RNA is similar to DNA."),
            _msg("user", "And proteins?"),
        ]
        session = MagicMock()
        _, turns = load_history_turns(session, session_id=1)
        assert turns == [
            ("What is RNA?", "RNA is similar to DNA."),
            ("And proteins?", ""),
        ]

    @patch("domain.chat.session_memory.list_recent_chat_messages")
    @patch("domain.chat.session_memory.latest_system_summary", return_value="")
    def test_orphan_assistant_message(self, _sum: MagicMock, mock_msgs: MagicMock) -> None:
        """An assistant message without a preceding user message."""
        mock_msgs.return_value = [
            _msg("assistant", "Welcome!"),
            _msg("user", "Hi"),
            _msg("assistant", "How can I help?"),
        ]
        session = MagicMock()
        _, turns = load_history_turns(session, session_id=1)
        assert turns == [
            ("", "Welcome!"),
            ("Hi", "How can I help?"),
        ]

    @patch("domain.chat.session_memory.list_recent_chat_messages")
    @patch("domain.chat.session_memory.latest_system_summary", return_value="")
    def test_adjacent_user_messages(self, _sum: MagicMock, mock_msgs: MagicMock) -> None:
        """Two user messages in a row (no assistant reply for first)."""
        mock_msgs.return_value = [
            _msg("user", "First question"),
            _msg("user", "Second question"),
            _msg("assistant", "Answer to second"),
        ]
        session = MagicMock()
        _, turns = load_history_turns(session, session_id=1)
        assert turns == [
            ("First question", ""),
            ("Second question", "Answer to second"),
        ]

    @patch("domain.chat.session_memory.list_recent_chat_messages")
    @patch("domain.chat.session_memory.latest_system_summary", return_value="")
    def test_empty_payload_skipped(self, _sum: MagicMock, mock_msgs: MagicMock) -> None:
        """Messages with empty text are filtered out."""
        mock_msgs.return_value = [
            _msg("user", ""),
            _msg("user", "Real question"),
            _msg("assistant", "Real answer"),
        ]
        session = MagicMock()
        _, turns = load_history_turns(session, session_id=1)
        assert turns == [("Real question", "Real answer")]

    @patch("domain.chat.session_memory.list_recent_chat_messages")
    @patch("domain.chat.session_memory.latest_system_summary", return_value="")
    def test_non_dict_messages_skipped(self, _sum: MagicMock, mock_msgs: MagicMock) -> None:
        """Non-dict or bad payload messages are safely ignored."""
        mock_msgs.return_value = [
            {"type": "user", "payload": "not a dict"},
            _msg("user", "Good message"),
            _msg("assistant", "Good reply"),
        ]
        session = MagicMock()
        _, turns = load_history_turns(session, session_id=1)
        assert turns == [("Good message", "Good reply")]
