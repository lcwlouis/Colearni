"""Graph LLM client adapters using OpenAI and LiteLLM SDKs."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from core.contracts import TutorTextStream
from core.observability import (
    SPAN_KIND_LLM,
    classify_usage_source,
    create_span,
    emit_event,
    extract_token_usage,
    get_observation_context,
    set_llm_span_attributes,
    set_prompt_metadata,
    set_usage_source,
    start_span,
)
from core.prompting import PromptRegistry

log = logging.getLogger("adapters.llm.providers")

_registry = PromptRegistry()

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

    # Model prefixes known to support reasoning params (e.g. reasoning_effort).
    _REASONING_CAPABLE_PREFIXES = ("o1", "o3", "o4")

    def __init__(
        self,
        *,
        model: str,
        timeout_seconds: float,
        json_temperature: float = 0.0,
        tutor_temperature: float = 0.0,
        provider: str,
        reasoning_enabled: bool = False,
        reasoning_effort: str | None = None,
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
        self._reasoning_enabled = reasoning_enabled
        self._reasoning_effort = reasoning_effort

    def extract_raw_graph(self, *, chunk_text: str) -> Mapping[str, Any]:
        prompt_meta = None
        try:
            prompt, prompt_meta = _registry.render_with_meta(
                "graph_extract_chunk_v1", {"chunk_text": chunk_text}
            )
        except Exception:
            prompt = f"Extract concept+edge JSON from this chunk.\n\nCHUNK:\n{chunk_text}"
        return self._chat_json(
            schema_name="graph_raw_extraction",
            schema=_RAW_GRAPH_SCHEMA,
            prompt=prompt,
            prompt_meta=prompt_meta,
        )

    def disambiguate(
        self,
        *,
        raw_name: str,
        context_snippet: str | None,
        candidates: Sequence[Mapping[str, object]],
    ) -> Mapping[str, Any]:
        candidates_json = json.dumps(list(candidates), ensure_ascii=True)
        prompt_meta = None
        try:
            prompt, prompt_meta = _registry.render_with_meta("graph_disambiguate_v1", {
                "raw_name": raw_name,
                "context_snippet": context_snippet or "",
                "candidates_json": candidates_json,
            })
        except Exception:
            prompt = (
                "Choose MERGE_INTO or CREATE_NEW.\n"
                f"RAW_NAME: {raw_name}\n"
                f"CONTEXT: {context_snippet or ''}\n"
                f"CANDIDATES_JSON: {candidates_json}"
            )
        return self._chat_json(
            schema_name="graph_disambiguation",
            schema=_DISAMBIGUATION_SCHEMA,
            prompt=prompt,
            prompt_meta=prompt_meta,
        )

    def generate_tutor_text(self, *, prompt: str, prompt_meta: Any | None = None) -> str:
        text, _ = self.generate_tutor_text_traced(prompt=prompt, prompt_meta=prompt_meta)
        return text

    def generate_tutor_text_traced(self, *, prompt: str, prompt_meta: Any | None = None) -> tuple[str, "GenerationTrace"]:
        """Generate tutor text and return (text, trace) tuple."""
        from core.schemas.assistant import GenerationTrace  # noqa: PLC0415

        text, trace = self._chat_text_traced(
            prompt=prompt,
            system_instruction=(
                "You are a grounded tutor. Follow style instructions exactly and stay concise."
            ),
            prompt_meta=prompt_meta,
        )
        return text, trace

    def generate_tutor_text_stream(
        self,
        *,
        prompt: str,
        prompt_meta: Any | None = None,
        reasoning_effort_override: str | None = None,
    ) -> TutorTextStream:
        """Stream tutor text, yielding deltas. Trace available after iteration.

        ``reasoning_effort_override`` is a reserved seam for future first-layer
        per-call effort selection.  When set, it overrides the settings-level
        effort and the trace records ``reasoning_effort_source="override"``.
        """
        messages = [
            {"role": "system", "content": "You are a grounded tutor. Follow style instructions exactly and stay concise."},
            {"role": "user", "content": prompt},
        ]
        supported = self._model_supports_reasoning()
        used = self._reasoning_enabled and supported
        if reasoning_effort_override is not None and used:
            effort = reasoning_effort_override
            effort_source = "override"
        else:
            effort = self._reasoning_effort if used else None
            effort_source = "settings" if effort is not None else None
        # "none" means disable explicit reasoning — no params sent to provider
        if effort == "none":
            used = False
            effort = None
            effort_source = None
        stream_obj = TutorTextStream(
            self._iter_nothing(),  # placeholder, replaced below
            provider=self._provider,
            model=self._model,
            reasoning_requested=self._reasoning_enabled,
            reasoning_supported=supported,
            reasoning_used=used,
            reasoning_effort=effort,
            reasoning_effort_source=effort_source,
        )
        stream_obj._delta_iter = self._stream_with_usage(
            messages=messages,
            temperature=self._tutor_temperature,
            stream_obj=stream_obj,
            prompt_meta=prompt_meta,
            rendered_length=len(prompt) if prompt_meta else None,
            effort_override=reasoning_effort_override if used else None,
        )
        return stream_obj

    @staticmethod
    def _iter_nothing() -> Iterator[str]:
        return iter(())

    def _model_supports_reasoning(self) -> bool:
        """Check if the current model supports reasoning params."""
        model_lower = self._model.lower()
        return any(model_lower.startswith(p) for p in self._REASONING_CAPABLE_PREFIXES)

    def _build_reasoning_kwargs(self, *, effort_override: str | None = None) -> dict[str, Any]:
        """Build capability-gated reasoning params with configurable effort.

        ``effort_override`` overrides the instance-level ``_reasoning_effort``
        when set.  Reserved for the future per-call override seam.
        """
        if not self._reasoning_enabled:
            return {}
        if not self._model_supports_reasoning():
            log.debug(
                "reasoning requested but model %s/%s does not support it; skipping",
                self._provider, self._model,
            )
            return {}
        effort = effort_override or self._reasoning_effort or "medium"
        if effort == "none":
            return {}
        return {"reasoning_effort": effort}

    def _stream_with_usage(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        stream_obj: TutorTextStream,
        prompt_meta: Any | None = None,
        rendered_length: int | None = None,
        effort_override: str | None = None,
    ) -> Iterator[str]:
        """Stream text deltas inside an LLM span and capture final usage.

        Uses create_span (not start_span) because this is a generator that
        yields across Starlette's thread-pool boundary.  start_span calls
        tracer.start_as_current_span which attaches a ContextVar token; if the
        generator resumes in a different thread context the subsequent detach
        raises ``ValueError: Token was created in a different Context``.
        """
        context = get_observation_context()
        operation = str(context.get("operation") or "llm.stream")
        span_name = f"llm.{operation}" if not operation.startswith("llm.") else operation
        collected_text: list[str] = []

        span = create_span(
            span_name,
            kind=SPAN_KIND_LLM,
            component="llm",
            operation=operation,
            provider=self._provider,
            model=self._model,
        )
        set_llm_span_attributes(
            span,
            model=self._model,
            invocation_params={
                "model": self._model,
                "temperature": temperature,
                "provider": self._provider,
                "stream": True,
            },
            messages=messages,
        )
        set_prompt_metadata(span, prompt_meta, rendered_length=rendered_length)

        last_chunk: Mapping[str, Any] = {}
        try:
            for chunk in self._sdk_stream_call(
                messages=messages,
                temperature=temperature,
                effort_override=effort_override,
            ):
                last_chunk = chunk
                delta_content = self._extract_stream_delta(chunk)
                if delta_content:
                    collected_text.append(delta_content)
                    yield delta_content
        except Exception as exc:
            emit_event(
                "llm.call",
                status="failure",
                component="llm",
                operation=operation,
                provider=self._provider,
                model=self._model,
                error_type=type(exc).__name__,
            )
            if span is not None:
                from opentelemetry import trace as _trace
                span.set_status(_trace.StatusCode.ERROR, str(exc))
                span.record_exception(exc)
                span.end()
            raise

        # Extract usage from the final chunk
        usage = self.extract_stream_usage(last_chunk)
        reasoning_tokens = self._extract_reasoning_tokens(last_chunk)
        stream_obj.set_usage(
            prompt_tokens=usage.get("token_prompt"),
            completion_tokens=usage.get("token_completion"),
            total_tokens=usage.get("token_total"),
            reasoning_tokens=reasoning_tokens,
        )

        response_text = "".join(collected_text)
        set_llm_span_attributes(
            span,
            response_message=response_text,
            token_usage=usage,
        )

        emit_event(
            "llm.call",
            status="success",
            component="llm",
            operation=operation,
            provider=self._provider,
            model=self._model,
            **usage,
        )

        if span is not None:
            from opentelemetry import trace as _trace
            span.set_status(_trace.StatusCode.OK)
            span.end()

    @staticmethod
    def _extract_reasoning_tokens(payload: Mapping[str, Any]) -> int | None:
        """Extract reasoning token count from provider responses when available."""
        usage = payload.get("usage")
        if not isinstance(usage, Mapping):
            return None
        # OpenAI: completion_tokens_details.reasoning_tokens
        details = usage.get("completion_tokens_details")
        if isinstance(details, Mapping):
            val = details.get("reasoning_tokens")
            if isinstance(val, int):
                return val
        return None

    def _chat_json(
        self,
        *,
        schema_name: str,
        schema: dict[str, object],
        prompt: str,
        prompt_meta: Any | None = None,
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
            prompt_meta=prompt_meta,
            rendered_length=len(prompt) if prompt_meta else None,
        )
        content = self._extract_content(result)
        response_payload = json.loads(content)
        if not isinstance(response_payload, dict):
            raise ValueError("Graph LLM response payload must decode to an object")
        return response_payload

    def _chat_text(self, *, prompt: str, system_instruction: str) -> str:
        text, _ = self._chat_text_traced(prompt=prompt, system_instruction=system_instruction)
        return text

    def _chat_text_traced(
        self,
        *,
        prompt: str,
        system_instruction: str,
        prompt_meta: Any | None = None,
        reasoning_effort_override: str | None = None,
    ) -> tuple[str, "GenerationTrace"]:
        """Return (text, trace) from a non-streaming LLM call.

        ``reasoning_effort_override`` is a reserved seam for future first-layer
        per-call effort selection.
        """
        import time as _time  # noqa: PLC0415

        from core.schemas.assistant import GenerationTrace  # noqa: PLC0415

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ]
        t0 = _time.monotonic_ns()
        result = self._call_with_observability(
            messages=messages,
            temperature=self._tutor_temperature,
            response_format=None,
            prompt_meta=prompt_meta,
            rendered_length=len(prompt) if prompt_meta else None,
        )
        elapsed_ms = round((_time.monotonic_ns() - t0) / 1_000_000, 2)
        text = self._extract_content(result).strip()
        usage = extract_token_usage(result)
        reasoning = self._extract_reasoning_tokens(result)
        supported = self._model_supports_reasoning()
        used = self._reasoning_enabled and supported
        if reasoning_effort_override is not None and used:
            effort = reasoning_effort_override
            effort_source = "override"
        else:
            effort = self._reasoning_effort if used else None
            effort_source = "settings" if effort is not None else None
        # "none" means disable explicit reasoning — no params sent to provider
        if effort == "none":
            used = False
            effort = None
            effort_source = None
        trace = GenerationTrace(
            provider=self._provider,
            model=self._model,
            timing_ms=elapsed_ms,
            prompt_tokens=usage.get("token_prompt"),
            completion_tokens=usage.get("token_completion"),
            total_tokens=usage.get("token_total"),
            reasoning_tokens=reasoning,
            reasoning_requested=self._reasoning_enabled,
            reasoning_supported=supported,
            reasoning_used=used,
            reasoning_effort=effort,
            reasoning_effort_source=effort_source,
        )
        return text, trace

    def _call_with_observability(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        response_format: dict[str, object] | None,
        prompt_meta: Any | None = None,
        rendered_length: int | None = None,
    ) -> Mapping[str, Any]:
        """Wrap the SDK call with observability spans and events."""
        context = get_observation_context()
        operation = str(context.get("operation") or "llm.call")
        span_name = f"llm.{operation}" if not operation.startswith("llm.") else operation

        with start_span(
            span_name,
            kind=SPAN_KIND_LLM,
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
            set_prompt_metadata(span, prompt_meta, rendered_length=rendered_length)

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

    @abstractmethod
    def _sdk_stream_call(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        effort_override: str | None = None,
    ) -> Iterator[Mapping[str, Any]]:
        """Execute a provider-specific streaming SDK call and yield raw chunk dicts."""

    @staticmethod
    def _extract_stream_delta(chunk: Mapping[str, Any]) -> str | None:
        """Extract text delta content from a streaming chunk."""
        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        delta = choices[0]
        if isinstance(delta, Mapping):
            delta_msg = delta.get("delta")
            if isinstance(delta_msg, Mapping):
                content = delta_msg.get("content")
                if isinstance(content, str):
                    return content
        return None

    @staticmethod
    def extract_stream_usage(chunk: Mapping[str, Any]) -> dict[str, int | None]:
        """Extract usage from a streaming chunk (typically the final one)."""
        return extract_token_usage(chunk)

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
        reasoning_enabled: bool = False,
        reasoning_effort: str | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("OpenAI API key is required for graph_llm_provider=openai")
        super().__init__(
            model=model,
            timeout_seconds=timeout_seconds,
            json_temperature=json_temperature,
            tutor_temperature=tutor_temperature,
            provider="openai",
            reasoning_enabled=reasoning_enabled,
            reasoning_effort=reasoning_effort,
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

    def _sdk_stream_call(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        effort_override: str | None = None,
    ) -> Iterator[Mapping[str, Any]]:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "temperature": temperature,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        kwargs.update(self._build_reasoning_kwargs(effort_override=effort_override))
        response = self._client.chat.completions.create(**kwargs)
        for chunk in response:
            yield chunk.model_dump() if hasattr(chunk, "model_dump") else dict(chunk)


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
        reasoning_enabled: bool = False,
        reasoning_effort: str | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("graph_llm base_url cannot be empty")
        super().__init__(
            model=model,
            timeout_seconds=timeout_seconds,
            json_temperature=json_temperature,
            tutor_temperature=tutor_temperature,
            provider="litellm",
            reasoning_enabled=reasoning_enabled,
            reasoning_effort=reasoning_effort,
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

    def _sdk_stream_call(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        effort_override: str | None = None,
    ) -> Iterator[Mapping[str, Any]]:
        import litellm  # noqa: PLC0415

        kwargs: dict[str, Any] = {
            "model": self._model,
            "temperature": temperature,
            "messages": messages,
            "api_base": self._base_url,
            "timeout": self._timeout_seconds,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if self._api_key is not None:
            kwargs["api_key"] = self._api_key
        kwargs.update(self._build_reasoning_kwargs(effort_override=effort_override))
        response = litellm.completion(**kwargs)
        for chunk in response:
            yield chunk.model_dump() if hasattr(chunk, "model_dump") else dict(chunk)
