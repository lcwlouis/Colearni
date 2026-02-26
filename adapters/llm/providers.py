"""Graph LLM client adapters for OpenAI-compatible chat completions APIs."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.observability import (
    emit_event,
    extract_token_usage,
    get_observation_context,
    set_llm_span_attributes,
    start_span,
)

_RAW_GRAPH_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"concepts": {"type": "array"}, "edges": {"type": "array"}},
    "required": ["concepts", "edges"],
    "additionalProperties": False,
}
_DISAMBIGUATION_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["MERGE_INTO", "CREATE_NEW"]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "merge_into_id": {"type": "integer"},
        "alias_to_add": {"type": "string"},
        "proposed_description": {"type": "string"},
    },
    "required": ["decision", "confidence"],
    "additionalProperties": False,
}


class _OpenAICompatibleGraphLLMClient:
    def __init__(
        self,
        *,
        model: str,
        timeout_seconds: float,
        base_url: str,
        api_key: str | None,
        provider: str,
    ) -> None:
        if not model.strip():
            raise ValueError("graph_llm model cannot be empty")
        if timeout_seconds <= 0:
            raise ValueError("graph_llm timeout_seconds must be positive")
        if not base_url.strip():
            raise ValueError("graph_llm base_url cannot be empty")
        self._model = model.strip()
        self._timeout_seconds = timeout_seconds
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key.strip() if api_key is not None and api_key.strip() else None
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
        payload: dict[str, object] = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": "Return only JSON that satisfies the provided schema.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
        }
        content = self._extract_message_content(self._post_chat_completion(payload))
        response_payload = json.loads(content)
        if not isinstance(response_payload, dict):
            raise ValueError("Graph LLM response payload must decode to an object")
        return response_payload

    def _chat_text(self, *, prompt: str, system_instruction: str) -> str:
        payload: dict[str, object] = {
            "model": self._model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
        }
        content = self._extract_message_content(self._post_chat_completion(payload))
        return content.strip()

    def _post_chat_completion(self, payload: Mapping[str, object]) -> Mapping[str, object]:
        headers = {"Content-Type": "application/json"}
        if self._api_key is not None:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = Request(
            self._url,
            data=json.dumps(dict(payload)).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        context = get_observation_context()
        operation = str(context.get("operation") or "llm.call")
        messages = payload.get("messages")

        with start_span(
            "llm.call",
            component="llm",
            operation=operation,
            provider=self._provider,
            model=self._model,
        ) as span:
            # Set OpenInference LLM attributes at the start of the span
            set_llm_span_attributes(
                span,
                model=self._model,
                invocation_params={
                    "model": self._model,
                    "temperature": payload.get("temperature", 0),
                    "provider": self._provider,
                },
                messages=list(messages) if isinstance(messages, (list, tuple)) else None,
            )

            try:
                with urlopen(request, timeout=self._timeout_seconds) as response:  # noqa: S310
                    response_body = response.read().decode("utf-8")
            except HTTPError as exc:
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
                body = exc.read().decode("utf-8", errors="replace") if exc.fp is not None else ""
                raise RuntimeError(
                    f"Graph LLM request failed with status {exc.code}: {body}"
                ) from exc
            except URLError as exc:
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
                raise RuntimeError(f"Graph LLM request failed: {exc.reason}") from exc

            try:
                parsed = json.loads(response_body)
            except json.JSONDecodeError as exc:
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
                raise
            if not isinstance(parsed, Mapping):
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
                    error_type=ValueError.__name__,
                )
                raise ValueError("Graph LLM response payload must decode to an object")

            token_usage = extract_token_usage(parsed)
            response_content = self._extract_message_content_safe(parsed)

            # Enrich span with response and token data
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
            return parsed

    def _extract_message_content(self, payload: Mapping[str, object]) -> str:
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

    def _extract_message_content_safe(self, payload: Mapping[str, object]) -> str | None:
        """Extract message content without raising — used for span attributes."""
        try:
            return self._extract_message_content(payload)
        except (ValueError, KeyError, TypeError):
            return None


class OpenAIGraphLLMClient(_OpenAICompatibleGraphLLMClient):
    def __init__(self, *, api_key: str, model: str, timeout_seconds: float) -> None:
        if not api_key.strip():
            raise ValueError("OpenAI API key is required for graph_llm_provider=openai")
        super().__init__(
            model=model,
            timeout_seconds=timeout_seconds,
            base_url="https://api.openai.com/v1",
            api_key=api_key,
            provider="openai",
        )


class LiteLLMGraphLLMClient(_OpenAICompatibleGraphLLMClient):
    def __init__(
        self,
        *,
        model: str,
        timeout_seconds: float,
        base_url: str,
        api_key: str | None = None,
    ) -> None:
        super().__init__(
            model=model,
            timeout_seconds=timeout_seconds,
            base_url=base_url,
            api_key=api_key,
            provider="litellm",
        )
