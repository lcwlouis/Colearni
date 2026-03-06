"""Tests for L2.1 — MessageStatus type and ChatMessageRecord.status field."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import get_args

import pytest
from pydantic import ValidationError

from core.schemas.chat import ChatMessageRecord, MessageStatus


class TestMessageStatusLiteral:
    """MessageStatus Literal has exactly the expected values."""

    def test_has_expected_values(self) -> None:
        assert set(get_args(MessageStatus)) == {
            "complete",
            "generating",
            "failed",
            "superseded",
        }


class TestChatMessageRecordStatus:
    """ChatMessageRecord accepts and defaults the status field."""

    @pytest.fixture()
    def _base_fields(self) -> dict:
        return {
            "message_id": 1,
            "session_id": 10,
            "type": "user",
            "payload": {"text": "hi"},
            "created_at": datetime.now(tz=timezone.utc),
        }

    def test_default_status_is_complete(self, _base_fields: dict) -> None:
        record = ChatMessageRecord(**_base_fields)
        assert record.status == "complete"

    def test_explicit_status_accepted(self, _base_fields: dict) -> None:
        for status in get_args(MessageStatus):
            record = ChatMessageRecord(**_base_fields, status=status)
            assert record.status == status

    def test_invalid_status_rejected(self, _base_fields: dict) -> None:
        with pytest.raises(ValidationError):
            ChatMessageRecord(**_base_fields, status="unknown")


class TestAppendChatMessageStatus:
    """append_chat_message() signature accepts an optional status parameter."""

    def test_default_status_parameter(self) -> None:
        import inspect

        from adapters.db.chat import append_chat_message

        sig = inspect.signature(append_chat_message)
        param = sig.parameters["status"]
        assert param.default == "complete"
