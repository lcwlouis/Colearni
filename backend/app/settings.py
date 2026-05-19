from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://colearni:colearni@localhost:5432/colearni"
    llm_provider: str = "openai"  # openai | openrouter | anthropic | gemini | deepseek
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_api_base: str = ""  # optional: override base URL (e.g. for local/custom endpoints)

    # Extended thinking / reasoning — off by default; silently skipped when
    # the selected model does not support it.
    llm_thinking_enabled: bool = False
    # Anthropic budget_tokens (min 1024); ignored for OpenAI-compatible providers.
    llm_thinking_budget: int = 8000
    # OpenAI o-series reasoning_effort: low | medium | high.
    llm_thinking_level: str = "medium"

    # Reasoning token visibility by provider:
    #   anthropic   — visible via native SDK thinking blocks (requires llm_thinking_enabled=true)
    #   openrouter  — visible with DeepSeek-R1 or similar reasoning-capable models.
    #   deepseek    — visible via reasoning_content field on the native DeepSeek endpoint
    #   openai      — uses the Responses API (client.responses.create) for ALL calls.
    #                 OpenAI never exposes raw reasoning tokens; only a human-readable
    #                 reasoning *summary* is returned via reasoning.summary='auto'.
    #                 Summaries stream as "thinking" SSE events when llm_thinking_enabled=true
    #                 AND an o-series / reasoning-capable model is selected.
    #                 With the default model (gpt-4o-mini) or llm_thinking_enabled=false,
    #                 no reasoning params are sent and no thinking events are emitted.


settings = Settings()
