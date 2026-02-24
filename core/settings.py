"""Application settings."""

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.schemas import GroundingMode


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
    ingest_populate_embeddings: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "APP_INGEST_POPULATE_EMBEDDINGS",
            "INGEST_POPULATE_EMBEDDINGS",
        ),
    )
    ingest_build_graph: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "APP_INGEST_BUILD_GRAPH",
            "INGEST_BUILD_GRAPH",
        ),
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
    default_grounding_mode: GroundingMode = Field(
        default=GroundingMode.HYBRID,
        validation_alias=AliasChoices(
            "APP_DEFAULT_GROUNDING_MODE",
            "DEFAULT_GROUNDING_MODE",
        ),
    )
    embedding_timeout_seconds: float = Field(
        default=15.0,
        validation_alias=AliasChoices(
            "APP_EMBEDDING_TIMEOUT_SECONDS",
            "EMBEDDING_TIMEOUT_SECONDS",
        ),
        gt=0,
    )
    graph_llm_provider: str = Field(
        default="openai",
        validation_alias=AliasChoices("APP_GRAPH_LLM_PROVIDER", "GRAPH_LLM_PROVIDER"),
    )
    graph_llm_model: str = Field(
        default="gpt-4.1-mini",
        validation_alias=AliasChoices("APP_GRAPH_LLM_MODEL", "GRAPH_LLM_MODEL"),
    )
    graph_llm_timeout_seconds: float = Field(
        default=30.0,
        validation_alias=AliasChoices(
            "APP_GRAPH_LLM_TIMEOUT_SECONDS",
            "GRAPH_LLM_TIMEOUT_SECONDS",
        ),
        gt=0,
    )
    litellm_base_url: str = Field(
        default="http://localhost:4000/v1",
        validation_alias=AliasChoices("APP_LITELLM_BASE_URL", "LITELLM_BASE_URL"),
    )
    litellm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_LITELLM_API_KEY", "LITELLM_API_KEY"),
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    litellm_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_LITELLM_MODEL", "LITELLM_MODEL"),
    )
    litellm_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_LITELLM_BASE_URL", "LITELLM_BASE_URL"),
    )
    litellm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_LITELLM_API_KEY", "LITELLM_API_KEY"),
    )
    resolver_lexical_top_k: int = Field(
        default=5,
        validation_alias=AliasChoices("APP_RESOLVER_LEXICAL_TOP_K", "RESOLVER_LEXICAL_TOP_K"),
        ge=1,
    )
    resolver_vector_top_k: int = Field(
        default=10,
        validation_alias=AliasChoices("APP_RESOLVER_VECTOR_TOP_K", "RESOLVER_VECTOR_TOP_K"),
        ge=1,
    )
    resolver_candidate_cap: int = Field(
        default=10,
        validation_alias=AliasChoices("APP_RESOLVER_CANDIDATE_CAP", "RESOLVER_CANDIDATE_CAP"),
        ge=1,
    )
    resolver_lexical_similarity_threshold: float = Field(
        default=0.85,
        validation_alias=AliasChoices(
            "APP_RESOLVER_LEXICAL_SIMILARITY_THRESHOLD",
            "RESOLVER_LEXICAL_SIMILARITY_THRESHOLD",
        ),
        ge=0.0,
        le=1.0,
    )
    resolver_lexical_margin_threshold: float = Field(
        default=0.10,
        validation_alias=AliasChoices(
            "APP_RESOLVER_LEXICAL_MARGIN_THRESHOLD",
            "RESOLVER_LEXICAL_MARGIN_THRESHOLD",
        ),
        ge=0.0,
        le=1.0,
    )
    resolver_vector_similarity_threshold: float = Field(
        default=0.92,
        validation_alias=AliasChoices(
            "APP_RESOLVER_VECTOR_SIMILARITY_THRESHOLD",
            "RESOLVER_VECTOR_SIMILARITY_THRESHOLD",
        ),
        ge=0.0,
        le=1.0,
    )
    resolver_vector_margin_threshold: float = Field(
        default=0.06,
        validation_alias=AliasChoices(
            "APP_RESOLVER_VECTOR_MARGIN_THRESHOLD",
            "RESOLVER_VECTOR_MARGIN_THRESHOLD",
        ),
        ge=0.0,
        le=1.0,
    )
    resolver_llm_confidence_floor: float = Field(
        default=0.65,
        validation_alias=AliasChoices(
            "APP_RESOLVER_LLM_CONFIDENCE_FLOOR",
            "RESOLVER_LLM_CONFIDENCE_FLOOR",
        ),
        ge=0.0,
        le=1.0,
    )
    resolver_max_llm_calls_per_chunk: int = Field(
        default=3,
        validation_alias=AliasChoices(
            "APP_RESOLVER_MAX_LLM_CALLS_PER_CHUNK",
            "RESOLVER_MAX_LLM_CALLS_PER_CHUNK",
        ),
        ge=0,
    )
    resolver_max_llm_calls_per_document: int = Field(
        default=50,
        validation_alias=AliasChoices(
            "APP_RESOLVER_MAX_LLM_CALLS_PER_DOCUMENT",
            "RESOLVER_MAX_LLM_CALLS_PER_DOCUMENT",
        ),
        ge=0,
    )
    resolver_concept_description_max_chars: int = Field(
        default=500,
        validation_alias=AliasChoices(
            "APP_RESOLVER_CONCEPT_DESCRIPTION_MAX_CHARS",
            "RESOLVER_CONCEPT_DESCRIPTION_MAX_CHARS",
        ),
        ge=32,
    )
    resolver_edge_description_max_chars: int = Field(
        default=300,
        validation_alias=AliasChoices(
            "APP_RESOLVER_EDGE_DESCRIPTION_MAX_CHARS",
            "RESOLVER_EDGE_DESCRIPTION_MAX_CHARS",
        ),
        ge=32,
    )
    resolver_edge_weight_cap: float = Field(
        default=10.0,
        validation_alias=AliasChoices("APP_RESOLVER_EDGE_WEIGHT_CAP", "RESOLVER_EDGE_WEIGHT_CAP"),
        ge=0.0,
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
        if normalized not in {"openai", "mock", "litellm"}:
            raise ValueError("embedding_provider must be one of: openai, mock, litellm")
        return normalized

    @field_validator("graph_llm_provider")
    @classmethod
    def validate_graph_llm_provider(cls, value: str) -> str:
        """Restrict graph LLM provider options."""
        normalized = value.strip().lower()
        if normalized not in {"openai", "litellm"}:
            raise ValueError("graph_llm_provider must be one of: openai, litellm")
        return normalized

    @field_validator("graph_llm_provider")
    @classmethod
    def validate_graph_llm_provider(cls, value: str) -> str:
        """Restrict graph LLM provider options."""
        normalized = value.strip().lower()
        if normalized not in {"openai", "litellm"}:
            raise ValueError("graph_llm_provider must be one of: openai, litellm")
        return normalized

    @field_validator("graph_llm_provider")
    @classmethod
    def validate_graph_llm_provider(cls, value: str) -> str:
        """Restrict graph LLM provider options."""
        normalized = value.strip().lower()
        if normalized not in {"openai", "litellm"}:
            raise ValueError("graph_llm_provider must be one of: openai, litellm")
        return normalized

    @field_validator("graph_llm_provider")
    @classmethod
    def validate_graph_llm_provider(cls, value: str) -> str:
        """Restrict graph LLM provider options."""
        normalized = value.strip().lower()
        if normalized not in {"openai", "litellm"}:
            raise ValueError("graph_llm_provider must be one of: openai, litellm")
        return normalized

    @field_validator("graph_llm_provider")
    @classmethod
    def validate_graph_llm_provider(cls, value: str) -> str:
        """Restrict graph LLM provider options."""
        normalized = value.strip().lower()
        if normalized not in {"openai", "litellm"}:
            raise ValueError("graph_llm_provider must be one of: openai, litellm")
        return normalized

    @field_validator("graph_llm_provider")
    @classmethod
    def validate_graph_llm_provider(cls, value: str) -> str:
        """Restrict graph LLM provider options."""
        normalized = value.strip().lower()
        if normalized not in {"openai", "litellm"}:
            raise ValueError("graph_llm_provider must be one of: openai, litellm")
        return normalized

    @field_validator("default_grounding_mode")
    @classmethod
    def validate_default_grounding_mode(
        cls,
        value: GroundingMode | str,
    ) -> GroundingMode:
        """Restrict grounded mode options."""
        if isinstance(value, GroundingMode):
            return value
        normalized = value.strip().lower()
        if normalized not in {GroundingMode.HYBRID.value, GroundingMode.STRICT.value}:
            raise ValueError("default_grounding_mode must be one of: hybrid, strict")
        return GroundingMode(normalized)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
