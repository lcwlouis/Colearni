"""Tests for LiteLLM JSON schema validation setting."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from core.settings import Settings


class TestJsonSchemaValidationSetting:
    """Verify the llm_json_schema_validation settings field."""

    def test_default_is_true(self) -> None:
        s = Settings()  # type: ignore[call-arg]
        assert s.llm_json_schema_validation is True

    def test_env_override(self) -> None:
        with patch.dict(
            "os.environ",
            {"APP_LLM_JSON_SCHEMA_VALIDATION": "false"},
        ):
            s = Settings()  # type: ignore[call-arg]
            assert s.llm_json_schema_validation is False


class TestLiteLLMClientJsonSchemaValidation:
    """Verify that LiteLLMGraphLLMClient toggles litellm flag."""

    def test_enabled_sets_flag(self) -> None:
        import litellm

        litellm.enable_json_schema_validation = False  # reset

        from adapters.llm.providers import LiteLLMGraphLLMClient

        LiteLLMGraphLLMClient(
            model="test-model",
            timeout_seconds=30,
            json_schema_validation=True,
        )
        assert litellm.enable_json_schema_validation is True

    def test_disabled_does_not_set_flag(self) -> None:
        import litellm

        litellm.enable_json_schema_validation = False  # reset

        from adapters.llm.providers import LiteLLMGraphLLMClient

        LiteLLMGraphLLMClient(
            model="test-model",
            timeout_seconds=30,
            json_schema_validation=False,
        )
        assert litellm.enable_json_schema_validation is False

    def test_default_param_enables(self) -> None:
        """Constructor default (no arg) should enable validation."""
        import litellm

        litellm.enable_json_schema_validation = False  # reset

        from adapters.llm.providers import LiteLLMGraphLLMClient

        LiteLLMGraphLLMClient(
            model="test-model",
            timeout_seconds=30,
        )
        assert litellm.enable_json_schema_validation is True
