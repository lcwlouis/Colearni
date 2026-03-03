"""Application settings."""

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.schemas import GroundingMode


class Settings(BaseSettings):
    """Minimal app settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_prefix="APP_",
        case_sensitive=False,
        extra="ignore",
    )

    env: str = "dev"
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("APP_LOG_LEVEL", "LOG_LEVEL"),
    )
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = Field(
        default=4,
        validation_alias=AliasChoices("APP_WORKERS", "WORKERS"),
        ge=1,
    )
    cors_allowed_origins: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("APP_CORS_ALLOWED_ORIGINS", "CORS_ALLOWED_ORIGINS"),
    )
    cors_allowed_methods: list[str] = Field(
        default_factory=lambda: ["*"],
        validation_alias=AliasChoices("APP_CORS_ALLOWED_METHODS", "CORS_ALLOWED_METHODS"),
    )
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
        default="mock",
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

    # ── Ingestion chunking ─────────────────────────────────────────────
    # All sizes are in characters (≈ 4 chars per token for English prose).
    # Vector chunks are stored in the DB and used for retrieval (small).
    # Graph chunks are larger text windows fed to the LLM extractor;
    # adjacent vector chunks are batched together to reach this size.
    # Set INGEST_GRAPH_CHUNK_SIZE=0 to use one LLM call per vector chunk.
    ingest_vector_chunk_size: int = Field(
        default=250,
        validation_alias=AliasChoices(
            "APP_INGEST_VECTOR_CHUNK_SIZE",
            "INGEST_VECTOR_CHUNK_SIZE",
        ),
        ge=10,
        description="Target size per vector chunk in the configured unit (words or chars).",
    )
    ingest_vector_chunk_overlap: int = Field(
        default=40,
        validation_alias=AliasChoices(
            "APP_INGEST_VECTOR_CHUNK_OVERLAP",
            "INGEST_VECTOR_CHUNK_OVERLAP",
        ),
        ge=0,
        description="Overlap between adjacent vector chunks in the configured unit.",
    )
    ingest_chunk_unit: str = Field(
        default="words",
        validation_alias=AliasChoices(
            "APP_INGEST_CHUNK_UNIT",
            "INGEST_CHUNK_UNIT",
        ),
        pattern=r"^(chars|words)$",
        description="Unit for chunk sizing: 'chars' or 'words'. Default 'words'.",
    )
    ingest_graph_chunk_size: int = Field(
        default=20000,
        validation_alias=AliasChoices(
            "APP_INGEST_GRAPH_CHUNK_SIZE",
            "INGEST_GRAPH_CHUNK_SIZE",
        ),
        ge=0,
        description=(
            "Target size per graph-extraction LLM window in the configured unit. "
            "Adjacent vector chunks are concatenated up to this size. "
            "0 = one LLM call per vector chunk."
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
        default="mock",
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
    graph_llm_json_temperature: float = Field(
        default=0.0,
        validation_alias=AliasChoices(
            "APP_GRAPH_LLM_JSON_TEMPERATURE",
            "GRAPH_LLM_JSON_TEMPERATURE",
        ),
        ge=0.0,
        le=2.0,
    )
    graph_llm_tutor_temperature: float = Field(
        default=0.0,
        validation_alias=AliasChoices(
            "APP_GRAPH_LLM_TUTOR_TEMPERATURE",
            "GRAPH_LLM_TUTOR_TEMPERATURE",
        ),
        ge=0.0,
        le=2.0,
    )
    observability_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("APP_OBSERVABILITY_ENABLED", "OBSERVABILITY_ENABLED"),
    )
    observability_otlp_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "APP_OBSERVABILITY_OTLP_ENDPOINT",
            "OBSERVABILITY_OTLP_ENDPOINT",
            "OTEL_EXPORTER_OTLP_ENDPOINT",
        ),
    )
    observability_service_name: str = Field(
        default="colearni-backend",
        validation_alias=AliasChoices(
            "APP_OBSERVABILITY_SERVICE_NAME",
            "OBSERVABILITY_SERVICE_NAME",
            "OTEL_SERVICE_NAME",
        ),
    )
    observability_record_content: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "APP_OBSERVABILITY_RECORD_CONTENT",
            "OBSERVABILITY_RECORD_CONTENT",
        ),
    )
    litellm_base_url: str = Field(
        default="http://localhost:4000/v1",
        validation_alias=AliasChoices("APP_LITELLM_BASE_URL", "LITELLM_BASE_URL"),
    )
    litellm_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_LITELLM_MODEL", "LITELLM_MODEL"),
    )
    litellm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_LITELLM_API_KEY", "LITELLM_API_KEY"),
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_OPENAI_API_KEY", "OPENAI_API_KEY"),
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
    resolver_disambiguate_batch_size: int = Field(
        default=5,
        description="Number of concepts to disambiguate in a single LLM call (1 = no batching)",
        validation_alias=AliasChoices(
            "APP_RESOLVER_DISAMBIGUATE_BATCH_SIZE",
            "RESOLVER_DISAMBIGUATE_BATCH_SIZE",
        ),
        ge=1,
        le=50,
    )
    gardener_max_llm_calls_per_run: int = Field(
        default=30,
        validation_alias=AliasChoices(
            "APP_GARDENER_MAX_LLM_CALLS_PER_RUN",
            "GARDENER_MAX_LLM_CALLS_PER_RUN",
        ),
        ge=0,
    )
    gardener_max_clusters_per_run: int = Field(
        default=50,
        validation_alias=AliasChoices(
            "APP_GARDENER_MAX_CLUSTERS_PER_RUN",
            "GARDENER_MAX_CLUSTERS_PER_RUN",
        ),
        ge=0,
    )
    gardener_max_dirty_nodes_per_run: int = Field(
        default=200,
        validation_alias=AliasChoices(
            "APP_GARDENER_MAX_DIRTY_NODES_PER_RUN",
            "GARDENER_MAX_DIRTY_NODES_PER_RUN",
        ),
        ge=1,
    )
    gardener_recent_window_days: int = Field(
        default=7,
        validation_alias=AliasChoices(
            "APP_GARDENER_RECENT_WINDOW_DAYS",
            "GARDENER_RECENT_WINDOW_DAYS",
        ),
        ge=1,
    )
    gardener_full_scan_max_seeds: int = Field(
        default=10000,
        validation_alias=AliasChoices(
            "APP_GARDENER_FULL_SCAN_MAX_SEEDS",
            "GARDENER_FULL_SCAN_MAX_SEEDS",
        ),
        ge=1,
    )
    gardener_full_scan_max_clusters: int = Field(
        default=500,
        validation_alias=AliasChoices(
            "APP_GARDENER_FULL_SCAN_MAX_CLUSTERS",
            "GARDENER_FULL_SCAN_MAX_CLUSTERS",
        ),
        ge=0,
    )
    gardener_full_scan_max_llm_calls: int = Field(
        default=200,
        validation_alias=AliasChoices(
            "APP_GARDENER_FULL_SCAN_MAX_LLM_CALLS",
            "GARDENER_FULL_SCAN_MAX_LLM_CALLS",
        ),
        ge=0,
    )
    gardener_full_scan_lexical_top_k: int = Field(
        default=20,
        validation_alias=AliasChoices(
            "APP_GARDENER_FULL_SCAN_LEXICAL_TOP_K",
            "GARDENER_FULL_SCAN_LEXICAL_TOP_K",
        ),
        ge=1,
    )
    gardener_full_scan_vector_top_k: int = Field(
        default=30,
        validation_alias=AliasChoices(
            "APP_GARDENER_FULL_SCAN_VECTOR_TOP_K",
            "GARDENER_FULL_SCAN_VECTOR_TOP_K",
        ),
        ge=1,
    )
    gardener_full_scan_candidate_cap: int = Field(
        default=30,
        validation_alias=AliasChoices(
            "APP_GARDENER_FULL_SCAN_CANDIDATE_CAP",
            "GARDENER_FULL_SCAN_CANDIDATE_CAP",
        ),
        ge=1,
    )

    # ── Auth settings ──────────────────────────────────────────────────
    auth_magic_link_ttl_minutes: int = Field(
        default=30,
        validation_alias=AliasChoices(
            "APP_AUTH_MAGIC_LINK_TTL_MINUTES",
            "AUTH_MAGIC_LINK_TTL_MINUTES",
        ),
        ge=1,
    )
    auth_session_ttl_days: int = Field(
        default=14,
        validation_alias=AliasChoices(
            "APP_AUTH_SESSION_TTL_DAYS",
            "AUTH_SESSION_TTL_DAYS",
        ),
        ge=1,
    )

    # ── Readiness / half-life settings ─────────────────────────────────
    readiness_cadence_hours: int = Field(
        default=24,
        validation_alias=AliasChoices(
            "APP_READINESS_CADENCE_HOURS",
            "READINESS_CADENCE_HOURS",
        ),
        ge=1,
    )
    readiness_half_life_days: float = Field(
        default=7.0,
        validation_alias=AliasChoices(
            "APP_READINESS_HALF_LIFE_DAYS",
            "READINESS_HALF_LIFE_DAYS",
        ),
        gt=0.0,
    )

    # ── Research agent settings ────────────────────────────────────────
    research_max_sources_per_workspace: int = Field(
        default=20,
        validation_alias=AliasChoices(
            "APP_RESEARCH_MAX_SOURCES_PER_WORKSPACE",
            "RESEARCH_MAX_SOURCES_PER_WORKSPACE",
        ),
        ge=1,
    )
    research_max_candidates_per_run: int = Field(
        default=50,
        validation_alias=AliasChoices(
            "APP_RESEARCH_MAX_CANDIDATES_PER_RUN",
            "RESEARCH_MAX_CANDIDATES_PER_RUN",
        ),
        ge=1,
    )

    # ── Prompt kit / persona ──────────────────────────────────────────
    tutor_persona: str = Field(
        default="colearni",
        validation_alias=AliasChoices("APP_TUTOR_PERSONA", "TUTOR_PERSONA"),
    )
    social_intent_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "APP_SOCIAL_INTENT_ENABLED",
            "SOCIAL_INTENT_ENABLED",
        ),
    )

    # ── Reasoning controls (per-task toggleable) ──────────────────────
    llm_reasoning_chat: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "APP_LLM_REASONING_CHAT",
            "LLM_REASONING_CHAT",
        ),
    )
    llm_reasoning_effort_chat: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "APP_LLM_REASONING_EFFORT_CHAT",
            "LLM_REASONING_EFFORT_CHAT",
        ),
    )
    llm_reasoning_effort_quiz_grading: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "APP_LLM_REASONING_EFFORT_QUIZ_GRADING",
            "LLM_REASONING_EFFORT_QUIZ_GRADING",
        ),
    )
    llm_reasoning_effort_graph_generation: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "APP_LLM_REASONING_EFFORT_GRAPH_GENERATION",
            "LLM_REASONING_EFFORT_GRAPH_GENERATION",
        ),
    )
    llm_reasoning_effort_quiz_generation: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "APP_LLM_REASONING_EFFORT_QUIZ_GENERATION",
            "LLM_REASONING_EFFORT_QUIZ_GENERATION",
        ),
    )

    # ── Reasoning summary (optional, ephemeral, never persisted) ──────
    reasoning_summary_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "APP_REASONING_SUMMARY_ENABLED",
            "REASONING_SUMMARY_ENABLED",
        ),
    )

    # ── Chat streaming ────────────────────────────────────────────────
    chat_streaming_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "APP_CHAT_STREAMING_ENABLED",
            "CHAT_STREAMING_ENABLED",
        ),
    )

    # ── Feature flags ─────────────────────────────────────────────────
    socratic_mode_default: bool = Field(
        default=False,
        description="Default state of the Socratic toggle in the tutor UI.",
        validation_alias=AliasChoices(
            "APP_SOCRATIC_MODE_DEFAULT",
            "SOCRATIC_MODE_DEFAULT",
        ),
    )
    include_dev_stats: bool = Field(
        default=False,
        description="Include generation_trace in chat API responses.",
        validation_alias=AliasChoices(
            "APP_INCLUDE_DEV_STATS",
            "INCLUDE_DEV_STATS",
        ),
    )

    llm_reasoning_quiz_grading: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "APP_LLM_REASONING_QUIZ_GRADING",
            "LLM_REASONING_QUIZ_GRADING",
        ),
    )
    llm_reasoning_graph_generation: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "APP_LLM_REASONING_GRAPH_GENERATION",
            "LLM_REASONING_GRAPH_GENERATION",
        ),
    )
    llm_reasoning_quiz_generation: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "APP_LLM_REASONING_QUIZ_GENERATION",
            "LLM_REASONING_QUIZ_GENERATION",
        ),
    )

    @model_validator(mode="after")
    def validate_vector_chunk_overlap(self) -> "Settings":
        """Ensure vector chunk overlap is strictly less than chunk size."""
        if self.ingest_vector_chunk_overlap >= self.ingest_vector_chunk_size:
            raise ValueError(
                "INGEST_VECTOR_CHUNK_OVERLAP must be less than INGEST_VECTOR_CHUNK_SIZE; "
                f"got overlap={self.ingest_vector_chunk_overlap} >= size={self.ingest_vector_chunk_size}"
            )
        return self

    @field_validator(
        "llm_reasoning_effort_chat",
        "llm_reasoning_effort_quiz_grading",
        "llm_reasoning_effort_graph_generation",
        "llm_reasoning_effort_quiz_generation",
        mode="before",
    )
    @classmethod
    def validate_reasoning_effort(cls, value: str | None) -> str | None:
        """Normalize and validate reasoning effort levels."""
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        allowed = {"none", "low", "medium", "high"}
        if normalized not in allowed:
            raise ValueError(
                f"reasoning_effort must be one of: {', '.join(sorted(allowed))}; got '{value}'"
            )
        return normalized

    @field_validator("cors_allowed_origins", "cors_allowed_methods", mode="before")
    @classmethod
    def assemble_cors_list(cls, value: str | list[str]) -> list[str]:
        """Parse comma-separated strings into lists."""
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

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
        if normalized not in {"openai", "litellm", "mock"}:
            raise ValueError("embedding_provider must be one of: openai, litellm, mock")
        return normalized

    @field_validator("graph_llm_provider")
    @classmethod
    def validate_graph_llm_provider(cls, value: str) -> str:
        """Restrict graph LLM provider options."""
        normalized = value.strip().lower()
        if normalized not in {"openai", "litellm", "mock"}:
            raise ValueError("graph_llm_provider must be one of: openai, litellm, mock")
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

    @field_validator("observability_otlp_endpoint")
    @classmethod
    def validate_observability_otlp_endpoint(cls, value: str | None) -> str | None:
        """Normalize blank observability endpoints to None."""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("observability_service_name")
    @classmethod
    def validate_observability_service_name(cls, value: str) -> str:
        """Require a non-empty service name when observability is enabled."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("observability_service_name must not be empty")
        return normalized


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
