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


def test_settings_reads_litellm_embedding_config_from_app_env(monkeypatch) -> None:
    """APP_ embedding env aliases should hydrate LiteLLM embedding settings."""
    monkeypatch.delenv("APP_EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("APP_LITELLM_MODEL", raising=False)
    monkeypatch.delenv("LITELLM_MODEL", raising=False)
    monkeypatch.setenv("APP_EMBEDDING_PROVIDER", "litellm")
    monkeypatch.setenv("APP_LITELLM_MODEL", "text-embedding-proxy")

    settings = Settings(_env_file=None)

    assert settings.embedding_provider == "litellm"
    assert settings.litellm_model == "text-embedding-proxy"


def test_settings_reads_litellm_embedding_config_from_legacy_env_aliases(monkeypatch) -> None:
    """Unprefixed env aliases should also hydrate LiteLLM embedding settings."""
    monkeypatch.delenv("APP_EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("APP_LITELLM_MODEL", raising=False)
    monkeypatch.delenv("LITELLM_MODEL", raising=False)
    monkeypatch.setenv("EMBEDDING_PROVIDER", "litellm")
    monkeypatch.setenv("LITELLM_MODEL", "text-embedding-proxy-legacy")

    settings = Settings(_env_file=None)

    assert settings.embedding_provider == "litellm"
    assert settings.litellm_model == "text-embedding-proxy-legacy"


def test_settings_reads_gardener_budget_aliases(monkeypatch) -> None:
    """Gardener env aliases should hydrate budget defaults from APP_ and legacy keys."""
    monkeypatch.setenv("APP_GARDENER_MAX_LLM_CALLS_PER_RUN", "12")
    monkeypatch.setenv("GARDENER_MAX_CLUSTERS_PER_RUN", "9")
    monkeypatch.setenv("APP_GARDENER_MAX_DIRTY_NODES_PER_RUN", "77")
    monkeypatch.setenv("GARDENER_RECENT_WINDOW_DAYS", "5")

    settings = Settings(_env_file=None)

    assert settings.gardener_max_llm_calls_per_run == 12
    assert settings.gardener_max_clusters_per_run == 9
    assert settings.gardener_max_dirty_nodes_per_run == 77
    assert settings.gardener_recent_window_days == 5


def test_settings_observability_defaults(monkeypatch) -> None:
    monkeypatch.delenv("APP_OBSERVABILITY_ENABLED", raising=False)
    monkeypatch.delenv("APP_OBSERVABILITY_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("APP_OBSERVABILITY_SERVICE_NAME", raising=False)

    settings = Settings(_env_file=None)

    assert settings.observability_enabled is False
    assert settings.observability_otlp_endpoint is None
    assert settings.observability_service_name == "colearni-backend"


def test_settings_reads_observability_aliases(monkeypatch) -> None:
    monkeypatch.setenv("OBSERVABILITY_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318/v1/traces")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "colearni-test")

    settings = Settings(_env_file=None)

    assert settings.observability_enabled is True
    assert settings.observability_otlp_endpoint == "http://127.0.0.1:4318/v1/traces"
    assert settings.observability_service_name == "colearni-test"
