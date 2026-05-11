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


settings = Settings()
