"""Application settings."""

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Minimal app settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        case_sensitive=False,
        extra="ignore",
    )

    env: str = "dev"
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = Field(
        default="postgresql+psycopg://colearni:colearni@localhost:5432/colearni",
        validation_alias=AliasChoices("APP_DATABASE_URL", "DATABASE_URL"),
    )
    embedding_dim: int = Field(
        default=1536,
        validation_alias=AliasChoices("APP_EMBEDDING_DIM", "EMBEDDING_DIM"),
        ge=1,
    )
    embedding_provider: str = Field(
        default="openai",
        validation_alias=AliasChoices("APP_EMBEDDING_PROVIDER", "EMBEDDING_PROVIDER"),
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        validation_alias=AliasChoices("APP_EMBEDDING_MODEL", "EMBEDDING_MODEL"),
    )
    embedding_batch_size: int = Field(
        default=32,
        validation_alias=AliasChoices("APP_EMBEDDING_BATCH_SIZE", "EMBEDDING_BATCH_SIZE"),
        ge=1,
    )
    embedding_backfill_max_chunks: int = Field(
        default=500,
        validation_alias=AliasChoices(
            "APP_EMBEDDING_BACKFILL_MAX_CHUNKS",
            "EMBEDDING_BACKFILL_MAX_CHUNKS",
        ),
        ge=1,
    )
    retrieval_max_top_k: int = Field(
        default=20,
        validation_alias=AliasChoices("APP_RETRIEVAL_MAX_TOP_K", "RETRIEVAL_MAX_TOP_K"),
        ge=1,
    )
    embedding_timeout_seconds: float = Field(
        default=15.0,
        validation_alias=AliasChoices(
            "APP_EMBEDDING_TIMEOUT_SECONDS",
            "EMBEDDING_TIMEOUT_SECONDS",
        ),
        gt=0,
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Ensure only Postgres DSNs are accepted."""
        if not value.startswith(("postgresql+psycopg://", "postgresql://")):
            raise ValueError("database_url must be a PostgreSQL DSN")
        return value

    @field_validator("embedding_provider")
    @classmethod
    def validate_embedding_provider(cls, value: str) -> str:
        """Restrict embedding provider options."""
        normalized = value.strip().lower()
        if normalized not in {"openai", "mock"}:
            raise ValueError("embedding_provider must be one of: openai, mock")
        return normalized


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
