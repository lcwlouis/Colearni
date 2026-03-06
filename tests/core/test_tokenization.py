"""Tests for core.tokenization."""

from __future__ import annotations

import sys
from unittest.mock import patch

from core.tokenization import count_text_tokens, truncate_to_tokens


class TestCountTextTokens:
    def test_uses_litellm_when_available(self):
        with patch("litellm.token_counter", return_value=42) as mock_tc:
            result = count_text_tokens("hello world", "gpt-4")
            assert result == 42
            mock_tc.assert_called_once_with(model="gpt-4", text="hello world")

    def test_falls_back_on_import_error(self):
        with patch.dict(sys.modules, {"litellm": None}):
            result = count_text_tokens("one two three", "gpt-4")
            # 3 words * 1.3 = 3.9 -> 3
            assert result == 3

    def test_falls_back_on_exception(self):
        with patch("litellm.token_counter", side_effect=Exception("boom")):
            result = count_text_tokens("one two three", "unknown-model")
            # 3 words * 1.3 = 3.9 -> 3
            assert result == 3

    def test_fallback_empty_string(self):
        with patch("litellm.token_counter", side_effect=Exception("boom")):
            result = count_text_tokens("", "gpt-4")
            assert result == 0


class TestTruncateToTokens:
    def test_truncate_fits_returns_unchanged(self):
        text = "short sentence"
        result = truncate_to_tokens(text, max_tokens=500, model="gpt-4o-mini")
        assert result == text

    def test_truncate_cuts_at_word_boundary(self):
        text = "one two three four five six seven eight nine ten " * 20
        result = truncate_to_tokens(text, max_tokens=10, model="gpt-4o-mini")
        body = result.removesuffix("…")
        # Body should consist only of whole words from the original text
        words = body.split()
        assert all(w in {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"} for w in words)
        assert len(result) < len(text)

    def test_truncate_empty_text(self):
        assert truncate_to_tokens("", max_tokens=100, model="gpt-4o-mini") == ""

    def test_truncate_appends_suffix(self):
        text = "one two three four five six seven eight nine ten " * 20
        result = truncate_to_tokens(text, max_tokens=10, model="gpt-4o-mini")
        assert result.endswith("…")
