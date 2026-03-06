"""Factory helpers for graph LLM providers."""

from core.contracts import GraphLLMClient
from core.settings import Settings, get_settings

from adapters.llm.providers import LiteLLMGraphLLMClient, OpenAIGraphLLMClient


def _non_empty_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


def _resolve_litellm_api_key(
    model: str,
    settings: Settings,
    api_base: str | None,
) -> str | None:
    """Resolve the API key for a LiteLLM model.

    In proxy mode (api_base set), use the shared proxy key.
    In direct mode, detect the provider from the model prefix and use
    the matching per-provider key, falling back to litellm_api_key.
    """
    if api_base:
        return _non_empty_or_none(settings.litellm_api_key)

    if "/" in model:
        prefix = model.split("/")[0].lower()
        if prefix == "openai":
            key = _non_empty_or_none(settings.openai_api_key)
            if key:
                return key
        elif prefix == "deepseek":
            key = _non_empty_or_none(settings.deepseek_api_key)
            if key:
                return key
        elif prefix == "gemini":
            key = _non_empty_or_none(settings.gemini_api_key)
            if key:
                return key
        elif prefix == "openrouter":
            key = _non_empty_or_none(settings.openrouter_api_key)
            if key:
                return key

    return _non_empty_or_none(settings.litellm_api_key)


def build_graph_llm_client(
    settings: Settings | None = None,
    timeout_override: float | None = None,
) -> GraphLLMClient:
    """Build the configured graph LLM client implementation."""
    active_settings = settings or get_settings()
    timeout = timeout_override or active_settings.graph_llm_timeout_seconds

    if active_settings.graph_llm_provider == "openai":
        api_key = active_settings.openai_api_key
        if api_key is None or not api_key.strip():
            raise ValueError(
                "APP_OPENAI_API_KEY (or OPENAI_API_KEY) must be set "
                "when APP_GRAPH_LLM_PROVIDER=openai"
            )
        return OpenAIGraphLLMClient(
            api_key=api_key,
            model=active_settings.graph_llm_model,
            timeout_seconds=timeout,
            json_temperature=active_settings.graph_llm_json_temperature,
            tutor_temperature=active_settings.graph_llm_tutor_temperature,
            reasoning_enabled=active_settings.llm_reasoning_chat,
            reasoning_effort=active_settings.llm_reasoning_effort_chat,
            max_retries=active_settings.llm_sdk_max_retries,
        )

    if active_settings.graph_llm_provider == "litellm":
        api_base = _non_empty_or_none(active_settings.litellm_base_url)
        api_key = _resolve_litellm_api_key(
            active_settings.graph_llm_model, active_settings, api_base,
        )
        return LiteLLMGraphLLMClient(
            model=active_settings.graph_llm_model,
            timeout_seconds=timeout,
            base_url=api_base,
            api_key=api_key,
            json_temperature=active_settings.graph_llm_json_temperature,
            tutor_temperature=active_settings.graph_llm_tutor_temperature,
            reasoning_enabled=active_settings.llm_reasoning_chat,
            reasoning_effort=active_settings.llm_reasoning_effort_chat,
            num_retries=active_settings.llm_sdk_max_retries,
            context_window_fallback_dict=active_settings.llm_context_window_fallbacks,
        )

    raise ValueError(f"Unsupported graph_llm_provider: {active_settings.graph_llm_provider}")


def build_tutor_llm_client(settings: Settings | None = None) -> GraphLLMClient:
    """Build the LLM client for tutor/chat operations.

    Uses tutor-specific model/provider settings if configured,
    otherwise falls back to the graph LLM settings.
    """
    active_settings = settings or get_settings()

    # If no tutor-specific model is set, fall back to graph client
    if active_settings.tutor_llm_model is None and active_settings.tutor_llm_provider is None:
        return build_graph_llm_client(settings=active_settings)

    # Resolve effective values with fallbacks
    provider = active_settings.tutor_llm_provider or active_settings.graph_llm_provider
    model = active_settings.tutor_llm_model or active_settings.graph_llm_model
    timeout = active_settings.tutor_llm_timeout_seconds or active_settings.graph_llm_timeout_seconds

    if provider == "openai":
        api_key = active_settings.openai_api_key
        if api_key is None or not api_key.strip():
            raise ValueError(
                "APP_OPENAI_API_KEY must be set when tutor provider is openai"
            )
        return OpenAIGraphLLMClient(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout,
            json_temperature=active_settings.graph_llm_json_temperature,
            tutor_temperature=active_settings.graph_llm_tutor_temperature,
            reasoning_enabled=active_settings.llm_reasoning_chat,
            reasoning_effort=active_settings.llm_reasoning_effort_chat,
            max_retries=active_settings.llm_sdk_max_retries,
        )

    if provider == "litellm":
        api_base = _non_empty_or_none(active_settings.litellm_base_url)
        api_key = _resolve_litellm_api_key(model, active_settings, api_base)
        return LiteLLMGraphLLMClient(
            model=model,
            timeout_seconds=timeout,
            base_url=api_base,
            api_key=api_key,
            json_temperature=active_settings.graph_llm_json_temperature,
            tutor_temperature=active_settings.graph_llm_tutor_temperature,
            reasoning_enabled=active_settings.llm_reasoning_chat,
            reasoning_effort=active_settings.llm_reasoning_effort_chat,
            num_retries=active_settings.llm_sdk_max_retries,
            context_window_fallback_dict=active_settings.llm_context_window_fallbacks,
        )

    raise ValueError(f"Unsupported tutor_llm_provider: {provider}")


def build_query_analyzer_llm_client(settings: Settings | None = None) -> GraphLLMClient:
    """Build the LLM client for query analysis.

    Uses query-analyzer-specific settings if configured,
    otherwise falls back to tutor, then graph LLM settings.
    """
    active_settings = settings or get_settings()

    if (
        active_settings.query_analyzer_llm_model is None
        and active_settings.query_analyzer_llm_provider is None
    ):
        return build_tutor_llm_client(settings=active_settings)

    provider = (
        active_settings.query_analyzer_llm_provider
        or active_settings.tutor_llm_provider
        or active_settings.graph_llm_provider
    )
    model = (
        active_settings.query_analyzer_llm_model
        or active_settings.tutor_llm_model
        or active_settings.graph_llm_model
    )
    timeout = (
        active_settings.query_analyzer_llm_timeout_seconds
        or active_settings.tutor_llm_timeout_seconds
        or active_settings.graph_llm_timeout_seconds
    )

    if provider == "openai":
        api_key = active_settings.openai_api_key
        if api_key is None or not api_key.strip():
            raise ValueError(
                "APP_OPENAI_API_KEY must be set when query analyzer provider is openai"
            )
        return OpenAIGraphLLMClient(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout,
            json_temperature=active_settings.graph_llm_json_temperature,
            tutor_temperature=active_settings.graph_llm_tutor_temperature,
            reasoning_enabled=False,
            reasoning_effort=None,
            max_retries=active_settings.llm_sdk_max_retries,
        )

    if provider == "litellm":
        api_base = _non_empty_or_none(active_settings.litellm_base_url)
        api_key = _resolve_litellm_api_key(model, active_settings, api_base)
        return LiteLLMGraphLLMClient(
            model=model,
            timeout_seconds=timeout,
            base_url=api_base,
            api_key=api_key,
            json_temperature=active_settings.graph_llm_json_temperature,
            tutor_temperature=active_settings.graph_llm_tutor_temperature,
            reasoning_enabled=False,
            reasoning_effort=None,
            num_retries=active_settings.llm_sdk_max_retries,
            context_window_fallback_dict=active_settings.llm_context_window_fallbacks,
        )

    raise ValueError(f"Unsupported query_analyzer_llm_provider: {provider}")

