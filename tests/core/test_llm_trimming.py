"""Tests for core.llm_trimming — trim_messages utility."""

from __future__ import annotations

from unittest.mock import patch

from core.llm_messages import Message
from core.llm_trimming import trim_messages

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MODEL = "gpt-4o"
MAX_TOKENS = 8000


def _msg(role: str, content: str) -> Message:
    return {"role": role, "content": content}


def _make_messages() -> list[Message]:
    """System prefix + 3-turn history + final user message."""
    return [
        _msg("system", "You are a tutor."),
        _msg("user", "old question 1"),
        _msg("assistant", "old answer 1"),
        _msg("user", "old question 2"),
        _msg("assistant", "old answer 2"),
        _msg("user", "latest question"),
    ]


# ---------------------------------------------------------------------------
# Under limit — no change
# ---------------------------------------------------------------------------


class TestUnderLimit:
    @patch("litellm.token_counter", return_value=100)
    @patch("litellm.get_max_tokens", return_value=MAX_TOKENS)
    def test_returns_unchanged(self, _mock_max: object, _mock_count: object) -> None:
        msgs = _make_messages()
        result = trim_messages(msgs, MODEL)
        assert result == msgs


# ---------------------------------------------------------------------------
# Over limit — trims oldest history
# ---------------------------------------------------------------------------


class TestOverLimit:
    @patch("litellm.get_max_tokens", return_value=MAX_TOKENS)
    def test_trims_oldest_history(self, _mock_max: object) -> None:
        msgs = _make_messages()

        # First call (full list) → over limit; after removing oldest pair → under.
        call_count = 0

        def fake_counter(*, model: str, messages: list[Message]) -> int:  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 7000  # initial: over limit (8000 * 0.8 = 6400)
            # Simulate: still over until oldest user+assistant pair removed.
            if len(messages) > 4:
                return 7000
            return 5000  # removed oldest pair → under

        with patch("litellm.token_counter", side_effect=fake_counter):
            result = trim_messages(msgs, MODEL)

        # System + remaining history + last user
        assert result[0] == _msg("system", "You are a tutor.")
        assert result[-1] == _msg("user", "latest question")
        # Oldest pair was dropped
        assert _msg("user", "old question 1") not in result
        assert _msg("assistant", "old answer 1") not in result


# ---------------------------------------------------------------------------
# System messages preserved
# ---------------------------------------------------------------------------


class TestSystemPreserved:
    @patch("litellm.get_max_tokens", return_value=MAX_TOKENS)
    def test_system_messages_always_kept(self, _mock_max: object) -> None:
        msgs = [
            _msg("system", "persona"),
            _msg("system", "context block"),
            _msg("user", "old q"),
            _msg("assistant", "old a"),
            _msg("user", "new q"),
        ]

        counter_calls = 0

        def fake_counter(*, model: str, messages: list[Message]) -> int:  # noqa: ARG001
            nonlocal counter_calls
            counter_calls += 1
            if counter_calls == 1:
                return 7000
            if len(messages) == 5:
                return 7000
            return 3000

        with patch("litellm.token_counter", side_effect=fake_counter):
            result = trim_messages(msgs, MODEL)

        assert result[0] == _msg("system", "persona")
        assert result[1] == _msg("system", "context block")
        assert result[-1] == _msg("user", "new q")


# ---------------------------------------------------------------------------
# Last user message preserved
# ---------------------------------------------------------------------------


class TestLastUserPreserved:
    @patch("litellm.get_max_tokens", return_value=MAX_TOKENS)
    def test_last_user_always_kept(self, _mock_max: object) -> None:
        msgs = _make_messages()

        counter_calls = 0

        def fake_counter(*, model: str, messages: list[Message]) -> int:  # noqa: ARG001
            nonlocal counter_calls
            counter_calls += 1
            if counter_calls == 1:
                return 7000
            # Always over until only system + last user remain.
            if len(messages) <= 2:
                return 1000
            return 7000

        with patch("litellm.token_counter", side_effect=fake_counter):
            result = trim_messages(msgs, MODEL)

        assert result[-1] == _msg("user", "latest question")
        assert result[0] == _msg("system", "You are a tutor.")
        assert len(result) == 2


# ---------------------------------------------------------------------------
# litellm unavailable — returns unchanged
# ---------------------------------------------------------------------------


class TestLitellmUnavailable:
    def test_import_error_returns_unchanged(self) -> None:
        import sys

        msgs = _make_messages()
        saved = sys.modules.get("litellm")
        sys.modules["litellm"] = None  # type: ignore[assignment]
        try:
            # Force re-import to trigger ImportError
            result = trim_messages(msgs, MODEL)
            assert result == msgs
        finally:
            if saved is None:
                sys.modules.pop("litellm", None)
            else:
                sys.modules["litellm"] = saved

    @patch("litellm.get_max_tokens", side_effect=Exception("boom"))
    def test_get_max_tokens_error_returns_unchanged(
        self, _mock: object
    ) -> None:
        msgs = _make_messages()
        result = trim_messages(msgs, MODEL)
        assert result == msgs

    @patch("litellm.token_counter", side_effect=Exception("boom"))
    @patch("litellm.get_max_tokens", return_value=MAX_TOKENS)
    def test_token_counter_error_returns_unchanged(
        self, _mock_max: object, _mock_count: object
    ) -> None:
        msgs = _make_messages()
        result = trim_messages(msgs, MODEL)
        assert result == msgs


# ---------------------------------------------------------------------------
# Only system + user (no history) — unchanged even if over limit
# ---------------------------------------------------------------------------


class TestNoHistory:
    @patch("litellm.token_counter", return_value=7000)
    @patch("litellm.get_max_tokens", return_value=MAX_TOKENS)
    def test_no_history_returns_unchanged(
        self, _mock_max: object, _mock_count: object
    ) -> None:
        msgs = [
            _msg("system", "You are a tutor."),
            _msg("user", "question"),
        ]
        result = trim_messages(msgs, MODEL)
        assert result == msgs

    @patch("litellm.token_counter", return_value=7000)
    @patch("litellm.get_max_tokens", return_value=MAX_TOKENS)
    def test_empty_messages(self, _mock_max: object, _mock_count: object) -> None:
        result = trim_messages([], MODEL)
        assert result == []
