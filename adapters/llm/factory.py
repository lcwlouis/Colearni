"""Factory helpers for graph LLM providers."""

from __future__ import annotations

import threading
from typing import Any

from core.contracts import GraphLLMClient
from core.settings import Settings, get_settings

from adapters.llm.providers import LiteLLMGraphLLMClient, OpenAIGraphLLMClient

# ── Module-level client cache ────────────────────────────────────────
_client_cache: dict[tuple[Any, ...], GraphLLMClient] = {}
_cache_lock = threading.Lock()


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


def _resolve_api_key_for_cache(
    provider: str,
    model: str,
    settings: Settings,
) -> str | None:
    """Resolve the effective API key used for a given provider/model combo."""
    if provider == "openai":
        return _non_empty_or_none(settings.openai_api_key)
    if provider == "litellm":
        api_base = _non_empty_or_none(settings.litellm_base_url)
        return _resolve_litellm_api_key(model, settings, api_base)
    return None


def build_graph_llm_client(
    settings: Settings | None = None,
    timeout_override: float | None = None,
) -> GraphLLMClient:
    """Build the configured graph LLM client implementation."""
    active_settings = settings or get_settings()
    timeout = timeout_override or active_settings.graph_llm_timeout_seconds

    api_key = _resolve_api_key_for_cache(
        active_settings.graph_llm_provider,
        active_settings.graph_llm_model,
        active_settings,
    )

    cache_key = (
        "graph",
        active_settings.graph_llm_provider,
        active_settings.graph_llm_model,
        timeout,
        active_settings.graph_llm_json_temperature,
        active_settings.graph_llm_tutor_temperature,
        active_settings.llm_reasoning_chat,
        active_settings.llm_reasoning_effort_chat,
        active_settings.llm_sdk_max_retries,
        api_key,
        _non_empty_or_none(active_settings.litellm_base_url),
    )

    if api_key is not None:
        with _cache_lock:
            cached = _client_cache.get(cache_key)
            if cached is not None:
                return cached

    if active_settings.graph_llm_provider == "openai":
        api_key_val = active_settings.openai_api_key
        if api_key_val is None or not api_key_val.strip():
            raise ValueError(
                "APP_OPENAI_API_KEY (or OPENAI_API_KEY) must be set "
                "when APP_GRAPH_LLM_PROVIDER=openai"
            )
        client: GraphLLMClient = OpenAIGraphLLMClient(
            api_key=api_key_val,
            model=active_settings.graph_llm_model,
            timeout_seconds=timeout,
            json_temperature=active_settings.graph_llm_json_temperature,
            tutor_temperature=active_settings.graph_llm_tutor_temperature,
            reasoning_enabled=active_settings.llm_reasoning_chat,
            reasoning_effort=active_settings.llm_reasoning_effort_chat,
            max_retries=active_settings.llm_sdk_max_retries,
        )

    elif active_settings.graph_llm_provider == "litellm":
        api_base = _non_empty_or_none(active_settings.litellm_base_url)
        litellm_key = _resolve_litellm_api_key(
            active_settings.graph_llm_model, active_settings, api_base,
        )
        client = LiteLLMGraphLLMClient(
            model=active_settings.graph_llm_model,
            timeout_seconds=timeout,
            base_url=api_base,
            api_key=litellm_key,
            json_temperature=active_settings.graph_llm_json_temperature,
            tutor_temperature=active_settings.graph_llm_tutor_temperature,
            reasoning_enabled=active_settings.llm_reasoning_chat,
            reasoning_effort=active_settings.llm_reasoning_effort_chat,
            num_retries=active_settings.llm_sdk_max_retries,
            context_window_fallback_dict=active_settings.llm_context_window_fallbacks,
            json_schema_validation=active_settings.llm_json_schema_validation,
        )

    else:
        raise ValueError(f"Unsupported graph_llm_provider: {active_settings.graph_llm_provider}")

    if api_key is not None:
        with _cache_lock:
            _client_cache[cache_key] = client
    return client


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

    api_key = _resolve_api_key_for_cache(provider, model, active_settings)

    cache_key = (
        "tutor",
        provider,
        model,
        timeout,
        active_settings.graph_llm_json_temperature,
        active_settings.graph_llm_tutor_temperature,
        active_settings.llm_reasoning_chat,
        active_settings.llm_reasoning_effort_chat,
        active_settings.llm_sdk_max_retries,
        api_key,
        _non_empty_or_none(active_settings.litellm_base_url),
    )

    if api_key is not None:
        with _cache_lock:
            cached = _client_cache.get(cache_key)
            if cached is not None:
                return cached

    if provider == "openai":
        api_key_val = active_settings.openai_api_key
        if api_key_val is None or not api_key_val.strip():
            raise ValueError(
                "APP_OPENAI_API_KEY must be set when tutor provider is openai"
            )
        client: GraphLLMClient = OpenAIGraphLLMClient(
            api_key=api_key_val,
            model=model,
            timeout_seconds=timeout,
            json_temperature=active_settings.graph_llm_json_temperature,
            tutor_temperature=active_settings.graph_llm_tutor_temperature,
            reasoning_enabled=active_settings.llm_reasoning_chat,
            reasoning_effort=active_settings.llm_reasoning_effort_chat,
            max_retries=active_settings.llm_sdk_max_retries,
        )

    elif provider == "litellm":
        api_base = _non_empty_or_none(active_settings.litellm_base_url)
        litellm_key = _resolve_litellm_api_key(model, active_settings, api_base)
        client = LiteLLMGraphLLMClient(
            model=model,
            timeout_seconds=timeout,
            base_url=api_base,
            api_key=litellm_key,
            json_temperature=active_settings.graph_llm_json_temperature,
            tutor_temperature=active_settings.graph_llm_tutor_temperature,
            reasoning_enabled=active_settings.llm_reasoning_chat,
            reasoning_effort=active_settings.llm_reasoning_effort_chat,
            num_retries=active_settings.llm_sdk_max_retries,
            context_window_fallback_dict=active_settings.llm_context_window_fallbacks,
            json_schema_validation=active_settings.llm_json_schema_validation,
        )

    else:
        raise ValueError(f"Unsupported tutor_llm_provider: {provider}")

    if api_key is not None:
        with _cache_lock:
            _client_cache[cache_key] = client
    return client


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

    api_key = _resolve_api_key_for_cache(provider, model, active_settings)

    cache_key = (
        "query_analyzer",
        provider,
        model,
        timeout,
        active_settings.graph_llm_json_temperature,
        active_settings.graph_llm_tutor_temperature,
        False,  # reasoning_enabled is always False for QA
        None,   # reasoning_effort is always None for QA
        active_settings.llm_sdk_max_retries,
        api_key,
        _non_empty_or_none(active_settings.litellm_base_url),
    )

    if api_key is not None:
        with _cache_lock:
            cached = _client_cache.get(cache_key)
            if cached is not None:
                return cached

    if provider == "openai":
        api_key_val = active_settings.openai_api_key
        if api_key_val is None or not api_key_val.strip():
            raise ValueError(
                "APP_OPENAI_API_KEY must be set when query analyzer provider is openai"
            )
        client: GraphLLMClient = OpenAIGraphLLMClient(
            api_key=api_key_val,
            model=model,
            timeout_seconds=timeout,
            json_temperature=active_settings.graph_llm_json_temperature,
            tutor_temperature=active_settings.graph_llm_tutor_temperature,
            reasoning_enabled=False,
            reasoning_effort=None,
            max_retries=active_settings.llm_sdk_max_retries,
        )

    elif provider == "litellm":
        api_base = _non_empty_or_none(active_settings.litellm_base_url)
        litellm_key = _resolve_litellm_api_key(model, active_settings, api_base)
        client = LiteLLMGraphLLMClient(
            model=model,
            timeout_seconds=timeout,
            base_url=api_base,
            api_key=litellm_key,
            json_temperature=active_settings.graph_llm_json_temperature,
            tutor_temperature=active_settings.graph_llm_tutor_temperature,
            reasoning_enabled=False,
            reasoning_effort=None,
            num_retries=active_settings.llm_sdk_max_retries,
            context_window_fallback_dict=active_settings.llm_context_window_fallbacks,
            json_schema_validation=active_settings.llm_json_schema_validation,
        )

    else:
        raise ValueError(f"Unsupported query_analyzer_llm_provider: {provider}")

    if api_key is not None:
        with _cache_lock:
            _client_cache[cache_key] = client
    return client

