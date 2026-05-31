from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://colearni:colearni@localhost:5432/colearni"
    source_storage_root: str = ".colearni/source-storage"
    llm_provider: str = "openai"  # openai | openrouter | anthropic | gemini | deepseek
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_api_base: str = ""  # optional: override base URL (e.g. for local/custom endpoints)

    # Extended thinking / reasoning — off by default; silently skipped when
    # the selected model does not support it.
    llm_thinking_enabled: bool = False
    # Anthropic budget_tokens (min 1024). Also used as extra request headroom
    # when provider reasoning consumes completion/output tokens.
    llm_thinking_budget: int = 8000
    # OpenAI o-series reasoning_effort: low | medium | high.
    llm_thinking_level: str = "medium"
    # Requested tutor answer budget per LLM call.
    llm_tutor_max_tokens: int = 4096

    # Tutor mode-selection (first) call: extended thinking/reasoning. Off by
    # default — the visible (second) answer call still respects llm_thinking_enabled.
    # Enabling this surfaces raw mode-selection reasoning in the trace.
    tutor_mode_selection_thinking: bool = False
    # Token cap for the first (mode-selection/classifier) LLM call. The first pass
    # only emits a single control line and stops, so it needs a tiny budget; the
    # visible answer (second call) still uses llm_tutor_max_tokens.
    tutor_mode_selection_max_tokens: int = 48
    # Per-turn retrieval tool-call budget (counts individual calls, incl. cached duplicates).
    tutor_tool_call_budget: int = 3
    # Per-tool-result character cap before truncation.
    tutor_max_tool_result_chars: int = 2000
    # Number of recent visible turns included in the prompt context window (verbatim).
    tutor_recent_visible_turns_limit: int = 10
    # Total character budget for all visible turns before summarization is triggered.
    # Roughly 60 k chars ≈ 15 k tokens (4 chars/token).  Short conversations never
    # pay the summarization cost; long ones are compressed before the window fills.
    tutor_history_char_budget: int = 60_000
    # Minimum number of new un-covered turns required before issuing a fresh LLM
    # summary call.  Prevents one-turn-at-a-time re-summarization.
    tutor_summary_batch_size: int = 5
    # Tutor-driven learner-state updates run at most once every N visible learner
    # turns (post-`done`, off the visible path). The observer itself still decides
    # whether an update is warranted, so most eligible turns are no-ops. Set to 0
    # to disable the tutor-driven update path entirely (quiz grading still updates).
    learner_state_update_interval: int = 4
    # Tokens allocated per node when calculating the graph generation token budget.
    # Budget = clamp(max_nodes * this, 4096, 16000).
    llm_generation_tokens_per_node: int = 300

    # Embedding provider — disabled by default; ILIKE search is used as fallback.
    embedding_provider: str = (
        "disabled"  # disabled | openai | gemini | ollama | openrouter | openai_compatible
    )
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: str = ""
    embedding_api_base: str = ""
    embedding_dim: int = 1536

    # Reranker — no-op by default. Interface stub ready for future providers.
    reranker_provider: str = "none"  # none | cohere | flashrank
    reranker_api_key: str = ""

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
