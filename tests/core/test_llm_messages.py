"""Tests for core.llm_messages — MessageBuilder and helpers."""

from __future__ import annotations

import pytest

from core.llm_messages import MessageBuilder, quick_messages

# ---------------------------------------------------------------------------
# MessageBuilder — happy path
# ---------------------------------------------------------------------------


class TestMessageBuilderBasic:
    """Core builder functionality."""

    def test_system_user_build(self) -> None:
        msgs = MessageBuilder().system("sys").user("usr").build()
        assert msgs == [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "usr"},
        ]

    def test_chaining_returns_self(self) -> None:
        builder = MessageBuilder()
        assert builder.system("s") is builder
        assert builder.user("u") is builder

    def test_assistant_message(self) -> None:
        msgs = (
            MessageBuilder()
            .system("sys")
            .user("q1")
            .assistant("a1")
            .user("q2")
            .build()
        )
        assert len(msgs) == 4
        assert msgs[2] == {"role": "assistant", "content": "a1"}

    def test_tool_message(self) -> None:
        msgs = (
            MessageBuilder()
            .system("sys")
            .user("call tool")
            .assistant("thinking")
            .tool("result", tool_call_id="call_123")
            .build()
        )
        assert msgs[-1] == {
            "role": "tool",
            "content": "result",
            "tool_call_id": "call_123",
        }

    def test_len_and_bool(self) -> None:
        b = MessageBuilder()
        assert len(b) == 0
        assert not b
        b.system("s")
        assert len(b) == 1
        assert b

    def test_messages_property_returns_copy(self) -> None:
        b = MessageBuilder().system("s").user("u")
        copy = b.messages
        copy.append({"role": "user", "content": "extra"})
        assert len(b) == 2  # original unchanged

    def test_build_returns_copy(self) -> None:
        b = MessageBuilder().system("s").user("u")
        result = b.build()
        result.append({"role": "user", "content": "extra"})
        assert len(b.build()) == 2


# ---------------------------------------------------------------------------
# Context blocks
# ---------------------------------------------------------------------------


class TestContextMessages:
    """Context block builder method."""

    def test_context_without_label(self) -> None:
        msgs = MessageBuilder().system("persona").context("doc summary").user("q").build()
        assert len(msgs) == 3
        assert msgs[1]["role"] == "system"
        assert msgs[1]["content"] == "doc summary"

    def test_context_with_label(self) -> None:
        msgs = (
            MessageBuilder()
            .system("persona")
            .context("summary text", label="documents")
            .user("q")
            .build()
        )
        ctx = msgs[1]["content"]
        assert "[documents]" in ctx
        assert "summary text" in ctx
        assert ctx.startswith("---")

    def test_multiple_context_blocks(self) -> None:
        msgs = (
            MessageBuilder()
            .system("persona")
            .context("docs", label="documents")
            .context("graph", label="graph")
            .context("assessment", label="assessment")
            .user("q")
            .build()
        )
        assert len(msgs) == 5
        assert all(m["role"] == "system" for m in msgs[:4])


# ---------------------------------------------------------------------------
# History turns
# ---------------------------------------------------------------------------


class TestHistoryTurns:
    """History turn-pair builder method."""

    def test_history_adds_pairs(self) -> None:
        turns = [("hi", "hello"), ("what is X?", "X is …")]
        msgs = MessageBuilder().system("sys").history(turns).user("next q").build()
        assert len(msgs) == 6  # sys + 2 pairs + user
        assert msgs[1] == {"role": "user", "content": "hi"}
        assert msgs[2] == {"role": "assistant", "content": "hello"}

    def test_history_skips_empty_strings(self) -> None:
        turns = [("", "orphan assistant"), ("user only", "")]
        msgs = MessageBuilder().system("sys").history(turns).user("q").build()
        # Empty strings skipped: only "orphan assistant", "user only", and final "q"
        assert len(msgs) == 4  # sys + assistant + user + user

    def test_empty_history(self) -> None:
        msgs = MessageBuilder().system("sys").history([]).user("q").build()
        assert len(msgs) == 2


# ---------------------------------------------------------------------------
# Validation — error cases
# ---------------------------------------------------------------------------


class TestMessageBuilderValidation:
    """Build-time validation rules."""

    def test_empty_builder_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            MessageBuilder().build()

    def test_last_message_must_be_user_or_tool(self) -> None:
        with pytest.raises(ValueError, match="user.*tool"):
            MessageBuilder().system("sys").build()

        with pytest.raises(ValueError, match="user.*tool"):
            MessageBuilder().system("sys").user("q").assistant("a").build()

    def test_system_after_non_system_raises(self) -> None:
        with pytest.raises(ValueError, match="[Ss]ystem.*before"):
            MessageBuilder().user("q").system("late system").user("q2").build()

    def test_system_after_assistant_raises(self) -> None:
        with pytest.raises(ValueError, match="[Ss]ystem.*before"):
            (
                MessageBuilder()
                .system("s")
                .user("q")
                .assistant("a")
                .system("late")
                .user("q2")
                .build()
            )


# ---------------------------------------------------------------------------
# Empty-content guard
# ---------------------------------------------------------------------------


class TestEmptyContentSkipped:
    """Empty strings are silently skipped by all builder methods."""

    def test_empty_system_skipped(self) -> None:
        b = MessageBuilder().system("").user("q")
        assert len(b) == 1

    def test_empty_user_skipped(self) -> None:
        b = MessageBuilder().system("s").user("")
        assert len(b) == 1

    def test_empty_assistant_skipped(self) -> None:
        b = MessageBuilder().system("s").assistant("").user("q")
        assert len(b) == 2

    def test_empty_context_skipped(self) -> None:
        b = MessageBuilder().system("s").context("").user("q")
        assert len(b) == 2

    def test_empty_tool_skipped(self) -> None:
        b = MessageBuilder().system("s").user("q").tool("", tool_call_id="x")
        assert len(b) == 2


# ---------------------------------------------------------------------------
# quick_messages helper
# ---------------------------------------------------------------------------


class TestQuickMessages:
    """Drop-in 2-message helper."""

    def test_basic(self) -> None:
        msgs = quick_messages("system text", "user text")
        assert msgs == [
            {"role": "system", "content": "system text"},
            {"role": "user", "content": "user text"},
        ]

    def test_type_is_list_of_message(self) -> None:
        msgs = quick_messages("s", "u")
        assert isinstance(msgs, list)
        assert all(isinstance(m, dict) for m in msgs)
        assert all("role" in m and "content" in m for m in msgs)
