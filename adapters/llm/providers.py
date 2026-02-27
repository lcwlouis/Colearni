"""Graph LLM client adapters using OpenAI and LiteLLM SDKs."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any

from core.observability import (
    emit_event,
    extract_token_usage,
    get_observation_context,
    set_llm_span_attributes,
    start_span,
)

_RAW_GRAPH_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "context_snippet": {"type": ["string", "null"]},
                    "description": {"type": ["string", "null"]},
                },
                "required": ["name", "context_snippet", "description"],
                "additionalProperties": False,
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "src_name": {"type": "string"},
                    "tgt_name": {"type": "string"},
                    "relation_type": {"type": "string"},
                    "description": {"type": ["string", "null"]},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "weight": {"type": "integer"},
                },
                "required": [
                    "src_name",
                    "tgt_name",
                    "relation_type",
                    "description",
                    "keywords",
                    "weight",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["concepts", "edges"],
    "additionalProperties": False,
}
_DISAMBIGUATION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["MERGE_INTO", "CREATE_NEW"]},
        "confidence": {"type": "number"},
        "merge_into_id": {"type": ["integer", "null"]},
        "alias_to_add": {"type": ["string", "null"]},
        "proposed_description": {"type": ["string", "null"]},
    },
    "required": ["decision", "confidence", "merge_into_id", "alias_to_add", "proposed_description"],
    "additionalProperties": False,
}


class _BaseGraphLLMClient(ABC):
    """Shared logic for observability, response parsing, and public interface."""

    def __init__(
        self,
        *,
        model: str,
        timeout_seconds: float,
        json_temperature: float = 0.0,
        tutor_temperature: float = 0.0,
        provider: str,
    ) -> None:
        if not model.strip():
            raise ValueError("graph_llm model cannot be empty")
        if timeout_seconds <= 0:
            raise ValueError("graph_llm timeout_seconds must be positive")
        if not 0.0 <= json_temperature <= 2.0:
            raise ValueError("graph_llm json_temperature must be between 0 and 2")
        if not 0.0 <= tutor_temperature <= 2.0:
            raise ValueError("graph_llm tutor_temperature must be between 0 and 2")
        self._model = model.strip()
        self._timeout_seconds = timeout_seconds
        self._json_temperature = float(json_temperature)
        self._tutor_temperature = float(tutor_temperature)
        self._provider = provider.strip() or "unknown"

    def extract_raw_graph(self, *, chunk_text: str) -> Mapping[str, Any]:
        return self._chat_json(
            schema_name="graph_raw_extraction",
            schema=_RAW_GRAPH_SCHEMA,
            prompt=f"Extract concept+edge JSON from this chunk.\n\nCHUNK:\n{chunk_text}",
        )

    def disambiguate(
        self,
        *,
        raw_name: str,
        context_snippet: str | None,
        candidates: Sequence[Mapping[str, object]],
    ) -> Mapping[str, Any]:
        return self._chat_json(
            schema_name="graph_disambiguation",
            schema=_DISAMBIGUATION_SCHEMA,
            prompt=(
                "Choose MERGE_INTO or CREATE_NEW.\n"
                f"RAW_NAME: {raw_name}\n"
                f"CONTEXT: {context_snippet or ''}\n"
                f"CANDIDATES_JSON: {json.dumps(list(candidates), ensure_ascii=True)}"
            ),
        )

    def generate_tutor_text(self, *, prompt: str) -> str:
        return self._chat_text(
            prompt=prompt,
            system_instruction=(
                "You are a grounded tutor. Follow style instructions exactly and stay concise."
            ),
        )

    def _chat_json(
        self,
        *,
        schema_name: str,
        schema: dict[str, object],
        prompt: str,
    ) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": "Return only JSON that satisfies the provided schema."},
            {"role": "user", "content": prompt},
        ]
        response_format = {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        }
        result = self._call_with_observability(
            messages=messages,
            temperature=self._json_temperature,
            response_format=response_format,
        )
        content = self._extract_content(result)
        response_payload = json.loads(content)
        if not isinstance(response_payload, dict):
            raise ValueError("Graph LLM response payload must decode to an object")
        return response_payload

    def _chat_text(self, *, prompt: str, system_instruction: str) -> str:
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ]
        result = self._call_with_observability(
            messages=messages,
            temperature=self._tutor_temperature,
            response_format=None,
        )
        return self._extract_content(result).strip()

    def _call_with_observability(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, object] | None,
    ) -> Mapping[str, Any]:
        """Wrap the SDK call with observability spans and events."""
        context = get_observation_context()
        operation = str(context.get("operation") or "llm.call")

        with start_span(
            "llm.call",
            component="llm",
            operation=operation,
            provider=self._provider,
            model=self._model,
        ) as span:
            set_llm_span_attributes(
                span,
                model=self._model,
                invocation_params={
                    "model": self._model,
                    "temperature": temperature,
                    "provider": self._provider,
                },
                messages=messages,
            )

            try:
                result = self._sdk_call(
                    messages=messages,
                    temperature=temperature,
                    response_format=response_format,
                )
            except Exception as exc:
                emit_event(
                    "llm.call",
                    status="failure",
                    component="llm",
                    operation=operation,
                    provider=self._provider,
                    model=self._model,
                    token_prompt=None,
                    token_completion=None,
                    token_total=None,
                    error_type=type(exc).__name__,
                )
                raise RuntimeError(
                    f"Graph LLM request failed: {exc}"
                ) from exc

            token_usage = extract_token_usage(result)
            response_content = self._extract_content_safe(result)

            set_llm_span_attributes(
                span,
                response_message=response_content,
                token_usage=token_usage,
            )
            emit_event(
                "llm.call",
                status="success",
                component="llm",
                operation=operation,
                provider=self._provider,
                model=self._model,
                **token_usage,
            )
            return result

    @abstractmethod
    def _sdk_call(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, object] | None,
    ) -> Mapping[str, Any]:
        """Execute the provider-specific SDK call and return the raw response dict."""

    @staticmethod
    def _extract_content(payload: Mapping[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Graph LLM response missing choices")
        first_choice = choices[0]
        if not isinstance(first_choice, Mapping):
            raise ValueError("Graph LLM response missing choice payload")
        message = first_choice.get("message")
        if not isinstance(message, Mapping):
            raise ValueError("Graph LLM response missing message")
        content = message.get("content")
        if isinstance(content, list):
            content = "".join(
                item.get("text", "")
                for item in content
                if isinstance(item, Mapping) and item.get("type") == "text"
            )
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Graph LLM response missing textual content")
        return content

    def _extract_content_safe(self, payload: Mapping[str, Any]) -> str | None:
        """Extract message content without raising — used for span attributes."""
        try:
            return self._extract_content(payload)
        except (ValueError, KeyError, TypeError):
            return None


class OpenAIGraphLLMClient(_BaseGraphLLMClient):
    """Graph LLM adapter using the official OpenAI Python SDK."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        json_temperature: float = 0.0,
        tutor_temperature: float = 0.0,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OpenAI API key is required for graph_llm_provider=openai")
        super().__init__(
            model=model,
            timeout_seconds=timeout_seconds,
            json_temperature=json_temperature,
            tutor_temperature=tutor_temperature,
            provider="openai",
        )
        from openai import OpenAI  # noqa: PLC0415

        self._client = OpenAI(api_key=api_key.strip(), timeout=timeout_seconds)

    def _sdk_call(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, object] | None,
    ) -> Mapping[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "temperature": temperature,
            "messages": messages,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        response = self._client.chat.completions.create(**kwargs)
        return response.model_dump()


class LiteLLMGraphLLMClient(_BaseGraphLLMClient):
    """Graph LLM adapter using the LiteLLM SDK."""

    def __init__(
        self,
        *,
        model: str,
        timeout_seconds: float,
        json_temperature: float = 0.0,
        tutor_temperature: float = 0.0,
        base_url: str,
        api_key: str | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("graph_llm base_url cannot be empty")
        super().__init__(
            model=model,
            timeout_seconds=timeout_seconds,
            json_temperature=json_temperature,
            tutor_temperature=tutor_temperature,
            provider="litellm",
        )
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key.strip() if api_key and api_key.strip() else None

    def _sdk_call(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, object] | None,
    ) -> Mapping[str, Any]:
        import litellm  # noqa: PLC0415

        kwargs: dict[str, Any] = {
            "model": self._model,
            "temperature": temperature,
            "messages": messages,
            "api_base": self._base_url,
            "timeout": self._timeout_seconds,
        }
        if self._api_key is not None:
            kwargs["api_key"] = self._api_key
        if response_format is not None:
            kwargs["response_format"] = response_format
        response = litellm.completion(**kwargs)
        return response.model_dump()
