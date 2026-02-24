"""Unit tests for settings environment alias behavior."""

from core.schemas import GroundingMode
from core.settings import Settings


def test_settings_reads_app_default_grounding_mode(monkeypatch) -> None:
    """Canonical APP_DEFAULT_GROUNDING_MODE should override default grounding mode."""
    monkeypatch.delenv("APP_DEFAULT_GROUNDING_MODE", raising=False)
    monkeypatch.delenv("DEFAULT_GROUNDING_MODE", raising=False)
    monkeypatch.delenv("DEFAULT_GROUNDED_MODE", raising=False)
    monkeypatch.setenv("APP_DEFAULT_GROUNDING_MODE", "strict")

    settings = Settings(_env_file=None)

    assert settings.default_grounding_mode == GroundingMode.STRICT


def test_settings_ignores_default_grounded_mode_typo(monkeypatch) -> None:
    """Legacy typo env key should not affect default grounding mode."""
    monkeypatch.delenv("APP_DEFAULT_GROUNDING_MODE", raising=False)
    monkeypatch.delenv("DEFAULT_GROUNDING_MODE", raising=False)
    monkeypatch.delenv("DEFAULT_GROUNDED_MODE", raising=False)
    monkeypatch.setenv("DEFAULT_GROUNDED_MODE", "strict")

    settings = Settings(_env_file=None)

    assert settings.default_grounding_mode == GroundingMode.HYBRID
