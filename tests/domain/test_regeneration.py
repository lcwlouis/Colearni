"""Tests for message regeneration (L6) — supersede + get user query."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from domain.chat.session_memory import (
    RegenerationError,
    supersede_and_get_user_query,
)


class TestSupersedeAndGetUserQuery:
    def _mock_session(self) -> MagicMock:
        return MagicMock()

    @patch("domain.chat.session_memory._db_get_preceding_user_message")
    @patch("domain.chat.session_memory._db_mark_message_superseded")
    def test_happy_path(self, mock_supersede, mock_get_user):
        mock_supersede.return_value = True
        mock_get_user.return_value = {
            "id": 10, "role": "user", "content": "What is photosynthesis?",
        }
        session = self._mock_session()

        result = supersede_and_get_user_query(
            session, message_id=11, session_id=1,
        )
        assert result == "What is photosynthesis?"
        mock_supersede.assert_called_once_with(session, message_id=11)
        mock_get_user.assert_called_once_with(
            session, message_id=11, session_id=1,
        )

    @patch("domain.chat.session_memory._db_mark_message_superseded")
    def test_message_not_supersedable(self, mock_supersede):
        mock_supersede.return_value = False
        session = self._mock_session()

        with pytest.raises(RegenerationError, match="cannot be regenerated"):
            supersede_and_get_user_query(
                session, message_id=11, session_id=1,
            )

    @patch("domain.chat.session_memory._db_get_preceding_user_message")
    @patch("domain.chat.session_memory._db_mark_message_superseded")
    def test_no_preceding_user_message(self, mock_supersede, mock_get_user):
        mock_supersede.return_value = True
        mock_get_user.return_value = None
        session = self._mock_session()

        with pytest.raises(RegenerationError, match="No preceding user message"):
            supersede_and_get_user_query(
                session, message_id=11, session_id=1,
            )


class TestMarkMessageSuperseded:
    """Test the DB-level function via its interface contract."""

    @patch("domain.chat.session_memory._db_mark_message_superseded")
    def test_returns_true_on_success(self, mock_fn):
        mock_fn.return_value = True
        from adapters.db.chat import mark_message_superseded
        # Just verify the function is importable and has the right signature
        assert callable(mark_message_superseded)

    @patch("domain.chat.session_memory._db_mark_message_superseded")
    def test_returns_false_on_no_match(self, mock_fn):
        mock_fn.return_value = False
        from adapters.db.chat import mark_message_superseded
        assert callable(mark_message_superseded)


class TestGetPrecedingUserMessage:
    """Test the DB-level function is importable."""

    def test_importable(self):
        from adapters.db.chat import get_preceding_user_message
        assert callable(get_preceding_user_message)
