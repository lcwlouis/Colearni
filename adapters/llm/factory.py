"""Factory helpers for graph LLM providers."""

from core.contracts import GraphLLMClient
from core.settings import Settings, get_settings

from adapters.llm.providers import LiteLLMGraphLLMClient, OpenAIGraphLLMClient


def build_graph_llm_client(settings: Settings | None = None) -> GraphLLMClient:
    """Build the configured graph LLM client implementation."""
    active_settings = settings or get_settings()

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
            timeout_seconds=active_settings.graph_llm_timeout_seconds,
            json_temperature=active_settings.graph_llm_json_temperature,
            tutor_temperature=active_settings.graph_llm_tutor_temperature,
            reasoning_enabled=active_settings.llm_reasoning_chat,
        )

    if active_settings.graph_llm_provider == "litellm":
        return LiteLLMGraphLLMClient(
            model=active_settings.graph_llm_model,
            timeout_seconds=active_settings.graph_llm_timeout_seconds,
            base_url=active_settings.litellm_base_url,
            api_key=active_settings.litellm_api_key,
            json_temperature=active_settings.graph_llm_json_temperature,
            tutor_temperature=active_settings.graph_llm_tutor_temperature,
            reasoning_enabled=active_settings.llm_reasoning_chat,
        )

    raise ValueError(f"Unsupported graph_llm_provider: {active_settings.graph_llm_provider}")

