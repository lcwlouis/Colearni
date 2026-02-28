"""Tests for U4: reasoning effort settings and trace semantics."""

from __future__ import annotations

import os

import pytest
from core.schemas.assistant import GenerationTrace
from core.settings import Settings


class TestReasoningEffortSettings:
    """U4: per-task reasoning effort settings."""

    def test_default_effort_is_none(self, monkeypatch) -> None:
        monkeypatch.delenv("APP_LLM_REASONING_EFFORT_CHAT", raising=False)
        monkeypatch.delenv("LLM_REASONING_EFFORT_CHAT", raising=False)
        monkeypatch.delenv("APP_LLM_REASONING_EFFORT_QUIZ_GRADING", raising=False)
        monkeypatch.delenv("LLM_REASONING_EFFORT_QUIZ_GRADING", raising=False)
        monkeypatch.delenv("APP_LLM_REASONING_EFFORT_GRAPH_GENERATION", raising=False)
        monkeypatch.delenv("LLM_REASONING_EFFORT_GRAPH_GENERATION", raising=False)
        monkeypatch.delenv("APP_LLM_REASONING_EFFORT_QUIZ_GENERATION", raising=False)
        monkeypatch.delenv("LLM_REASONING_EFFORT_QUIZ_GENERATION", raising=False)
        settings = Settings(_env_file=None)
        assert settings.llm_reasoning_effort_chat is None
        assert settings.llm_reasoning_effort_quiz_grading is None
        assert settings.llm_reasoning_effort_graph_generation is None
        assert settings.llm_reasoning_effort_quiz_generation is None

    def test_valid_effort_values(self, monkeypatch) -> None:
        for level in ("low", "medium", "high"):
            monkeypatch.setenv("APP_LLM_REASONING_EFFORT_CHAT", level)
            settings = Settings(_env_file=None)
            assert settings.llm_reasoning_effort_chat == level

    def test_effort_case_insensitive(self, monkeypatch) -> None:
        monkeypatch.setenv("APP_LLM_REASONING_EFFORT_CHAT", "HIGH")
        settings = Settings(_env_file=None)
        assert settings.llm_reasoning_effort_chat == "high"

    def test_invalid_effort_rejected(self, monkeypatch) -> None:
        monkeypatch.setenv("APP_LLM_REASONING_EFFORT_CHAT", "extreme")
        with pytest.raises(Exception):
            Settings(_env_file=None)

    def test_blank_effort_normalized_to_none(self, monkeypatch) -> None:
        monkeypatch.setenv("APP_LLM_REASONING_EFFORT_CHAT", "")
        settings = Settings(_env_file=None)
        assert settings.llm_reasoning_effort_chat is None

    def test_none_effort_accepted_and_normalized(self, monkeypatch) -> None:
        """'none' is a valid effort value meaning 'disable explicit reasoning'."""
        monkeypatch.setenv("APP_LLM_REASONING_EFFORT_CHAT", "none")
        settings = Settings(_env_file=None)
        assert settings.llm_reasoning_effort_chat == "none"

    def test_reasoning_summary_default_false(self, monkeypatch) -> None:
        monkeypatch.delenv("APP_REASONING_SUMMARY_ENABLED", raising=False)
        monkeypatch.delenv("REASONING_SUMMARY_ENABLED", raising=False)
        settings = Settings(_env_file=None)
        assert settings.reasoning_summary_enabled is False

    def test_env_file_loading_order(self, tmp_path, monkeypatch) -> None:
        """.env is loaded; .env.local overrides .env when present."""
        # Clear any OS-level env that would interfere
        monkeypatch.delenv("APP_LLM_REASONING_EFFORT_CHAT", raising=False)
        monkeypatch.delenv("LLM_REASONING_EFFORT_CHAT", raising=False)
        env_file = tmp_path / ".env"
        env_local = tmp_path / ".env.local"
        env_file.write_text("APP_LLM_REASONING_EFFORT_CHAT=low\n")
        # No .env.local yet — .env should be used
        settings = Settings(_env_file=(str(env_file),))
        assert settings.llm_reasoning_effort_chat == "low"
        # Now add .env.local that overrides
        env_local.write_text("APP_LLM_REASONING_EFFORT_CHAT=high\n")
        settings2 = Settings(_env_file=(str(env_file), str(env_local)))
        assert settings2.llm_reasoning_effort_chat == "high"


class TestGenerationTraceEffortFields:
    """U4: reasoning_effort and reasoning_effort_source on GenerationTrace."""

    def test_defaults_to_none(self) -> None:
        trace = GenerationTrace()
        assert trace.reasoning_effort is None
        assert trace.reasoning_effort_source is None

    def test_settings_source(self) -> None:
        trace = GenerationTrace(
            reasoning_requested=True,
            reasoning_supported=True,
            reasoning_used=True,
            reasoning_effort="high",
            reasoning_effort_source="settings",
        )
        assert trace.reasoning_effort == "high"
        assert trace.reasoning_effort_source == "settings"

    def test_override_source_reserved(self) -> None:
        trace = GenerationTrace(
            reasoning_effort="low",
            reasoning_effort_source="override",
        )
        assert trace.reasoning_effort_source == "override"

    def test_serialization_includes_effort_fields(self) -> None:
        trace = GenerationTrace(
            reasoning_effort="medium",
            reasoning_effort_source="settings",
        )
        data = trace.model_dump(mode="json")
        assert data["reasoning_effort"] == "medium"
        assert data["reasoning_effort_source"] == "settings"

    def test_effort_none_when_reasoning_not_used(self) -> None:
        """Effort should be None when reasoning was not used."""
        trace = GenerationTrace(
            reasoning_requested=False,
            reasoning_used=False,
            reasoning_effort=None,
            reasoning_effort_source=None,
        )
        assert trace.reasoning_effort is None

    def test_provider_tokens_without_explicit_reasoning(self) -> None:
        """Provider may report reasoning_tokens even when app did not request reasoning."""
        trace = GenerationTrace(
            reasoning_requested=False,
            reasoning_supported=True,
            reasoning_used=False,
            reasoning_effort=None,
            reasoning_effort_source=None,
            reasoning_tokens=1024,
        )
        assert trace.reasoning_requested is False
        assert trace.reasoning_used is False
        assert trace.reasoning_tokens == 1024
