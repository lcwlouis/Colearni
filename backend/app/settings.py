from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_version: str = "0.1.0"
    database_url: str = "postgresql+asyncpg://colearni:colearni@localhost:5432/colearni"
    llm_provider: str = "openai"  # openai | openrouter | anthropic | gemini | deepseek
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_api_base: str = ""  # optional: override base URL (e.g. for local/custom endpoints)

    # Extended thinking / reasoning — off by default; silently skipped when
    # the selected model does not support it.
    llm_thinking_enabled: bool = False
    llm_thinking_budget: int = 8000  # Anthropic: budget_tokens (min 1024); ignored for OpenAI-compatible
    llm_thinking_level: str = "medium"  # OpenAI o-series reasoning_effort: low | medium | high

    # Reasoning token visibility by provider:
    #   anthropic   — visible via native SDK thinking blocks (requires llm_thinking_enabled=true)
    #   openrouter  — visible when using DeepSeek-R1 or similar (reasoning_content / reasoning field)
    #   deepseek    — visible via reasoning_content field on the native DeepSeek endpoint
    #   openai      — NOT visible via Chat Completions API; OpenAI intentionally withholds raw
    #                 reasoning text. Only available via the Responses API with summary opt-in,
    #                 which uses a different endpoint and is not currently implemented.


settings = Settings()
