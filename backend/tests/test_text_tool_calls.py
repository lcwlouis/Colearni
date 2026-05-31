"""Recovery of tool calls a model emits as TEXT instead of native tool calls.

Small/local models (e.g. deepseek-v4-flash) sometimes print a
``<functioncall>{...}</functioncall>`` block in the visible text rather than
using the native tool-call channel. ``parse_text_tool_calls`` recovers those so
retrieval and the suggest_quiz/suggest_artifact CTAs still fire, and
``strip_text_tool_calls`` keeps the raw block from leaking to the learner.
"""

from __future__ import annotations

from backend.app.agents.provider_tools import (
    parse_text_tool_calls,
    strip_text_tool_calls,
)
from backend.app.agents.retrieval_tools import (
    SEARCH_SOURCES_TOOL,
    SUGGEST_ARTIFACT_TOOL,
    SUGGEST_QUIZ_TOOL,
)

_TOOLS = [SEARCH_SOURCES_TOOL, SUGGEST_QUIZ_TOOL, SUGGEST_ARTIFACT_TOOL]


def test_recovers_functioncall_block_for_suggest_artifact() -> None:
    text = (
        "I can suggest a learning artifact for you. <functioncall> "
        '{"name": "suggest_artifact", "arguments": {"kind": "timeline", '
        '"reason": "A timeline anchors the tracklist in order."}}</functioncall>'
    )
    calls = parse_text_tool_calls(text, _TOOLS)
    assert len(calls) == 1
    call = calls[0]
    assert call.is_valid
    assert call.name == "suggest_artifact"
    assert call.arguments["kind"] == "timeline"
    assert call.arguments["reason"]


def test_strip_removes_the_block_from_visible_text() -> None:
    text = (
        "Here is a thought.\n<functioncall> "
        '{"name": "suggest_quiz", "arguments": {"quiz_type": "practice", '
        '"reason": "ready for a quick check"}}</functioncall>'
    )
    cleaned = strip_text_tool_calls(text)
    assert "functioncall" not in cleaned
    assert "suggest_quiz" not in cleaned
    assert cleaned.startswith("Here is a thought.")


def test_recovers_unclosed_block() -> None:
    # Model truncated before emitting the closing tag.
    text = (
        '<functioncall> {"name": "suggest_quiz", '
        '"arguments": {"quiz_type": "level_up", "reason": "x"}}'
    )
    calls = parse_text_tool_calls(text, _TOOLS)
    assert len(calls) == 1
    assert calls[0].name == "suggest_quiz"
    assert calls[0].arguments["quiz_type"] == "level_up"
    assert strip_text_tool_calls(text) == ""


def test_recovers_bare_json_object() -> None:
    text = (
        '{"name": "suggest_artifact", '
        '"arguments": {"kind": "worked_example", "reason": "step it out"}}'
    )
    calls = parse_text_tool_calls(text, _TOOLS)
    assert len(calls) == 1
    assert calls[0].name == "suggest_artifact"
    assert calls[0].is_valid


def test_unknown_tool_name_is_ignored() -> None:
    text = '<functioncall> {"name": "definitely_not_a_tool", "arguments": {}}</functioncall>'
    assert parse_text_tool_calls(text, _TOOLS) == []


def test_invalid_arguments_carry_validation_error() -> None:
    # Unknown enum value for kind -> not valid; caller drops it.
    text = (
        '<functioncall> {"name": "suggest_artifact", '
        '"arguments": {"kind": "not_a_kind", "reason": "r"}}</functioncall>'
    )
    calls = parse_text_tool_calls(text, _TOOLS)
    assert len(calls) == 1
    assert not calls[0].is_valid


def test_plain_text_with_no_tool_call_is_untouched() -> None:
    text = "What do you already know about the album's themes?"
    assert parse_text_tool_calls(text, _TOOLS) == []
    assert strip_text_tool_calls(text) == text
