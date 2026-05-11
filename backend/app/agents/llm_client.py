"""Unified async LLM client with provider routing.

Supports OpenAI-compatible endpoints (OpenAI, OpenRouter, DeepSeek, Gemini) via the
openai SDK, and Anthropic natively via the anthropic SDK (lazy import).

Adding a new provider:
  1. Add an entry to PROVIDER_BASE_URLS (if OpenAI-compatible), OR
  2. Add a branch in LLMClient.chat() for custom SDK providers.

Usage:
    client = LLMClient.from_settings(settings)
    text = await client.chat([{"role": "user", "content": "Hello"}])
"""

from __future__ import annotations

from backend.app.settings import Settings

# OpenAI-compatible providers: base URL is all that differs.
# Empty string means "use SDK default" (i.e. api.openai.com).
PROVIDER_BASE_URLS: dict[str, str] = {
    "openai": "",
    "openrouter": "https://openrouter.ai/api/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
}

# Providers that use a non-OpenAI SDK
_NATIVE_SDK_PROVIDERS = {"anthropic"}

SUPPORTED_PROVIDERS = sorted(PROVIDER_BASE_URLS) + sorted(_NATIVE_SDK_PROVIDERS)


class LLMClient:
    """Async LLM client. All provider-specific wiring is encapsulated here.

    All SDKs are imported lazily so tests and imports that don't invoke the LLM
    never require the provider package to be installed.
    """

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        api_key: str,
        api_base: str = "",
    ) -> None:
        self._provider = provider.lower()
        self._model = model
        self._api_key = api_key
        # Explicit api_base overrides the built-in provider default.
        self._api_base = api_base

    @classmethod
    def from_settings(cls, s: Settings) -> LLMClient:
        return cls(
            provider=s.llm_provider,
            model=s.llm_model,
            api_key=s.llm_api_key,
            api_base=s.llm_api_base,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> str:
        """Send a chat-completion request and return the assistant text."""
        if self._provider in _NATIVE_SDK_PROVIDERS:
            return await self._anthropic_chat(messages, temperature, max_tokens)
        return await self._openai_compatible_chat(messages, temperature)

    # ------------------------------------------------------------------
    # OpenAI-compatible path (OpenAI, OpenRouter, DeepSeek, Gemini, custom)
    # ------------------------------------------------------------------

    def _openai_base_url(self) -> str:
        if self._api_base:
            return self._api_base
        return PROVIDER_BASE_URLS.get(self._provider, "")

    def _openai_client(self):  # type: ignore[return]
        from openai import AsyncOpenAI  # lazy

        kwargs: dict = {"api_key": self._api_key}
        base_url = self._openai_base_url()
        if base_url:
            kwargs["base_url"] = base_url
        return AsyncOpenAI(**kwargs)

    async def _openai_compatible_chat(self, messages: list[dict], temperature: float) -> str:
        client = self._openai_client()
        extra_headers: dict = {}
        if self._provider == "openrouter":
            # OpenRouter recommends these for routing and analytics.
            extra_headers = {
                "HTTP-Referer": "https://colearni.app",
                "X-Title": "CoLearni",
            }
        response = await client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            extra_headers=extra_headers or None,  # type: ignore[arg-type]
        )
        return response.choices[0].message.content or ""

    # ------------------------------------------------------------------
    # Anthropic native path
    # ------------------------------------------------------------------

    def _anthropic_client(self):  # type: ignore[return]
        from anthropic import AsyncAnthropic  # lazy

        return AsyncAnthropic(api_key=self._api_key)

    async def _anthropic_chat(
        self, messages: list[dict], temperature: float, max_tokens: int
    ) -> str:
        # Anthropic separates system messages from the turn list.
        system = ""
        turns: list[dict] = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                turns.append(msg)

        client = self._anthropic_client()
        kwargs: dict = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": turns,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system

        response = await client.messages.create(**kwargs)
        return response.content[0].text if response.content else ""
