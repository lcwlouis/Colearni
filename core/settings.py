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
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Ensure only Postgres DSNs are accepted."""
        if not value.startswith(("postgresql+psycopg://", "postgresql://")):
            raise ValueError("database_url must be a PostgreSQL DSN")
        return value


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
