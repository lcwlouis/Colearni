"""Graph LLM client adapters using OpenAI and LiteLLM SDKs."""

from __future__ import annotations

import json
import logging
import warnings
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from core.contracts import TutorTextStream
from core.llm_messages import Message, MessageBuilder
from core.observability import (
    LLM_REASONING_CONTENT,
    LLM_TOKEN_COUNT_REASONING,
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
from core.rate_limiter import get_llm_limiter

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
                    "tier": {
                        "type": ["string", "null"],
                        "enum": ["umbrella", "topic", "subtopic", "granular", None],
                    },
                },
                "required": ["name", "context_snippet", "description", "tier"],
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
        "decision": {"type": "string", "enum": ["MERGE_INTO", "CREATE_NEW", "LINK_ONLY"]},
        "confidence": {"type": "number"},
        "merge_into_id": {"type": ["integer", "null"]},
        "merge_into_name": {"type": ["string", "null"]},
        "alias_to_add": {"type": ["string", "null"]},
        "proposed_description": {"type": ["string", "null"]},
        "link_to_id": {"type": ["integer", "null"]},
        "link_to_name": {"type": ["string", "null"]},
        "link_relation_type": {"type": ["string", "null"]},
        "proposed_tier": {"type": ["string", "null"]},
    },
    "required": ["decision", "confidence", "merge_into_id", "merge_into_name", "alias_to_add", "proposed_description", "link_to_id", "link_to_name", "link_relation_type", "proposed_tier"],
    "additionalProperties": False,
}
_DISAMBIGUATION_BATCH_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "concept_ref": {"type": "string"},
                    "operations": {"type": "array", "items": _DISAMBIGUATION_SCHEMA},
                },
                "required": ["concept_ref", "operations"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["decisions"],
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

    # ── Providers that support OpenAI-style json_schema response_format ──
    _JSON_SCHEMA_PROVIDERS = frozenset({"openai"})

    # ── Prompt caching (Anthropic) ──
    _ANTHROPIC_PREFIXES = ("claude", "anthropic/")

    def _is_anthropic_model(self) -> bool:
        """Return True if the current model targets Anthropic."""
        model_lower = self._model.lower()
        return any(model_lower.startswith(p) for p in self._ANTHROPIC_PREFIXES)

    @staticmethod
    def _apply_cache_control(
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Annotate the first system message with ``cache_control`` for prompt caching.

        Returns a shallow copy with the first system message's ``content``
        transformed to the content-blocks format expected by Anthropic / LiteLLM.
        Subsequent messages are left unchanged.  Safe to call unconditionally;
        if there are no system messages the list is returned as-is.
        """
        result: list[dict[str, Any]] = []
        marked = False
        for msg in messages:
            msg_copy = dict(msg)
            if not marked and msg_copy.get("role") == "system":
                content = msg_copy.get("content", "")
                if isinstance(content, str) and content:
                    msg_copy["content"] = [
                        {
                            "type": "text",
                            "text": content,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ]
                marked = True
            result.append(msg_copy)
        return result

    def _prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply provider-specific message transformations before SDK calls.

        Currently adds ``cache_control`` to the first system message for
        Anthropic models.  Returns *messages* unmodified for other providers.
        """
        if self._is_anthropic_model():
            return self._apply_cache_control(messages)
        return messages

    def _model_supports_json_schema(self) -> bool:
        """Return True if the model supports ``{"type": "json_schema"}``."""
        if self._provider in self._JSON_SCHEMA_PROVIDERS:
            return True
        model_lower = self._model.lower()
        if model_lower.startswith("openai/") or "gpt-" in model_lower:
            return True
        return False

    def extract_raw_graph(self, *, chunk_text: str) -> Mapping[str, Any]:
        prompt_meta = None
        system_prompt = None
        try:
            system_prompt, _ = _registry.render_with_meta(
                "graph_extract_chunk_v1_system", {}
            )
            prompt, prompt_meta = _registry.render_with_meta(
                "graph_extract_chunk_v1", {"chunk_text": chunk_text}
            )
        except Exception:
            system_prompt = (
                "You are a knowledge graph extraction component for a learning system. "
                "Extract durable learning concepts and meaningful relationships from study material. "
                "Return valid JSON only."
            )
            prompt = f"Extract concept+edge JSON from this chunk.\n\nCHUNK:\n{chunk_text}"
        return self._chat_json(
            schema_name="graph_raw_extraction",
            schema=_RAW_GRAPH_SCHEMA,
            prompt=prompt,
            prompt_meta=prompt_meta,
            system_prompt=system_prompt,
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
        system_prompt = None
        try:
            system_prompt, _ = _registry.render_with_meta(
                "graph_disambiguate_v1_system", {}
            )
            prompt, prompt_meta = _registry.render_with_meta("graph_disambiguate_v1", {
                "raw_name": raw_name,
                "context_snippet": context_snippet or "",
                "candidates_json": candidates_json,
            })
        except Exception:
            system_prompt = (
                "You are a conservative graph resolver. "
                "Decide whether a raw concept should merge into an existing canonical concept or create a new one. "
                "Return valid JSON only."
            )
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
            system_prompt=system_prompt,
        )

    def disambiguate_batch(
        self,
        *,
        items: Sequence[Mapping[str, object]],
    ) -> Sequence[Mapping[str, Any]]:
        """Disambiguate multiple concepts, splitting into sub-batches if needed.

        Each item must have: raw_name, context_snippet, candidates.
        Returns list of decision dicts in input order.
        Falls back to individual calls on parse failure.
        """
        if not items:
            return []
        if len(items) == 1:
            item = items[0]
            result = self.disambiguate(
                raw_name=str(item["raw_name"]),
                context_snippet=str(item.get("context_snippet") or ""),
                candidates=list(item.get("candidates", [])),  # type: ignore[arg-type]
            )
            return [{"concept_ref": str(item["raw_name"]), "operations": [result]}]

        from core.settings import get_settings  # noqa: PLC0415

        settings = get_settings()
        max_tokens = settings.disambiguate_max_tokens_per_batch
        max_items = settings.disambiguate_max_items_per_batch
        overhead = 500  # estimated system-prompt tokens

        # Estimate tokens per item (rough chars-to-tokens ratio)
        item_tokens = [len(json.dumps(item, ensure_ascii=True)) // 4 for item in items]

        # Build sub-batches respecting token and item-count limits
        sub_batches: list[list[int]] = []
        current_batch: list[int] = []
        current_tokens = overhead
        for i, tokens in enumerate(item_tokens):
            if current_batch and (
                current_tokens + tokens > max_tokens
                or len(current_batch) >= max_items
            ):
                sub_batches.append(current_batch)
                current_batch = [i]
                current_tokens = overhead + tokens
            else:
                current_batch.append(i)
                current_tokens += tokens
        if current_batch:
            sub_batches.append(current_batch)

        if len(sub_batches) == 1:
            return self._disambiguate_batch_single_call(items)

        log.info(
            "Splitting %d items into %d sub-batches for disambiguation",
            len(items),
            len(sub_batches),
        )
        all_results: list[Mapping[str, Any] | None] = [None] * len(items)
        for indices in sub_batches:
            sub_items = [items[i] for i in indices]
            sub_results = self._disambiguate_batch_single_call(sub_items)
            for idx, result in zip(indices, sub_results):
                all_results[idx] = result
        return all_results  # type: ignore[return-value]

    def _disambiguate_batch_single_call(
        self,
        items: Sequence[Mapping[str, object]],
    ) -> Sequence[Mapping[str, Any]]:
        """Send a single batch of items to the LLM for disambiguation."""
        batch_payload = []
        for item in items:
            entry: dict[str, Any] = {
                "raw_name": item["raw_name"],
                "context_snippet": item.get("context_snippet") or "",
                "candidates": list(item.get("candidates", [])),
            }
            if "own_id" in item:
                entry["own_id"] = item["own_id"]
            if "own_tier" in item:
                entry["own_tier"] = item["own_tier"]
            batch_payload.append(entry)
        batch_json = json.dumps(batch_payload, ensure_ascii=True)

        prompt_meta = None
        system_prompt = None
        try:
            system_prompt, _ = _registry.render_with_meta(
                "graph_disambiguate_batch_v1_system", {}
            )
            prompt, prompt_meta = _registry.render_with_meta(
                "graph_disambiguate_batch_v1",
                {"batch_items_json": batch_json},
            )
        except Exception:
            system_prompt = (
                "You are a conservative graph resolver. "
                "For each concept, decide MERGE_INTO, CREATE_NEW, or LINK_ONLY. "
                "Return JSON with a 'decisions' array."
            )
            prompt = (
                "Resolve each concept below.\n\n"
                f"{batch_json}"
            )

        raw = self._chat_json(
            schema_name="graph_disambiguation_batch",
            schema=_DISAMBIGUATION_BATCH_SCHEMA,
            prompt=prompt,
            prompt_meta=prompt_meta,
            system_prompt=system_prompt,
        )
        decisions = raw.get("decisions", [])
        if not isinstance(decisions, list):
            log.warning("Batch disambiguation returned non-list decisions; treating all as CREATE_NEW")
            decisions = []

        # Build lookup by concept_ref for robust matching
        decision_by_ref: dict[str, Any] = {}
        for dec in decisions:
            if isinstance(dec, dict) and dec.get("concept_ref"):
                decision_by_ref[dec["concept_ref"]] = dec

        # Ensure we have exactly one decision per item (fill CREATE_NEW for missing)
        result: list[Any] = []
        missing_count = 0
        for item in items:
            raw_name = str(item["raw_name"])
            if raw_name in decision_by_ref:
                result.append(decision_by_ref[raw_name])
            else:
                missing_count += 1
                result.append({
                    "concept_ref": raw_name,
                    "operations": [{
                        "decision": "CREATE_NEW",
                        "confidence": 0.0,
                        "merge_into_id": None,
                        "merge_into_name": None,
                        "alias_to_add": None,
                        "proposed_description": None,
                        "link_to_id": None,
                        "link_to_name": None,
                        "link_relation_type": None,
                        "proposed_tier": None,
                    }],
                })

        if missing_count > 0:
            log.warning(
                "Batch disambiguation returned %d/%d decisions; filled %d with CREATE_NEW",
                len(decisions), len(items), missing_count,
            )
        return result

    def generate_tutor_text(self, *, prompt: str, prompt_meta: Any | None = None, system_prompt: str | None = None) -> str:
        """.. deprecated:: Use complete_messages() instead."""
        warnings.warn(
            "generate_tutor_text is deprecated, use complete_messages instead",
            DeprecationWarning,
            stacklevel=2,
        )
        text, _ = self.generate_tutor_text_traced(prompt=prompt, prompt_meta=prompt_meta, system_prompt=system_prompt)
        return text

    def generate_tutor_text_traced(self, *, prompt: str, prompt_meta: Any | None = None, system_prompt: str | None = None) -> tuple[str, "GenerationTrace"]:
        """Generate tutor text and return (text, trace) tuple.

        .. deprecated:: Use complete_messages() instead.
        """
        warnings.warn(
            "generate_tutor_text_traced is deprecated, use complete_messages instead",
            DeprecationWarning,
            stacklevel=2,
        )
        text, trace = self._chat_text_traced(
            prompt=prompt,
            system_instruction=(
                system_prompt
                or "You are a grounded tutor. Follow style instructions exactly and stay concise."
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
        operation: str | None = None,
        system_prompt: str | None = None,
    ) -> TutorTextStream:
        """Stream tutor text, yielding deltas. Trace available after iteration.

        .. deprecated:: Use stream_messages() instead.

        ``system_prompt`` overrides the default system instruction.  When the
        prompt builder returns a ``PromptMessages``, callers should pass
        ``system_prompt=messages.system`` and ``prompt=messages.user``.

        ``reasoning_effort_override`` is a reserved seam for future first-layer
        per-call effort selection.  When set, it overrides the settings-level
        effort and the trace records ``reasoning_effort_source="override"``.

        ``operation`` names the LLM span for Phoenix.  Defaults to the
        active observation context's ``operation`` field, then ``llm.stream``.
        """
        warnings.warn(
            "generate_tutor_text_stream is deprecated, use stream_messages instead",
            DeprecationWarning,
            stacklevel=2,
        )
        messages: list[Message] = [
            {"role": "system", "content": system_prompt or "You are a grounded tutor. Follow style instructions exactly and stay concise."},
            {"role": "user", "content": prompt},
        ]
        return self.stream_messages(
            messages,
            prompt_meta=prompt_meta,
            reasoning_effort_override=reasoning_effort_override,
            operation=operation or "",
        )

    # -- messages[]-native methods -----------------------------------------

    def stream_messages(
        self,
        messages: list[Message],
        *,
        prompt_meta: Any | None = None,
        reasoning_effort_override: str | None = None,
        operation: str = "",
    ) -> TutorTextStream:
        """Stream LLM response from pre-built messages.

        This is the ``messages[]``-native entry point for streaming calls.
        ``generate_tutor_text_stream`` delegates here after constructing a
        simple two-message list.
        """
        supported = self._model_supports_reasoning()
        used = self._reasoning_enabled and supported
        if reasoning_effort_override is not None and used:
            effort = reasoning_effort_override
            effort_source = "override"
        else:
            effort = self._reasoning_effort if used else None
            effort_source = "settings" if effort is not None else None
        if effort == "none":
            used = False
            effort = None
            effort_source = None
        stream_obj = TutorTextStream(
            self._iter_nothing(),
            provider=self._provider,
            model=self._model,
            reasoning_requested=self._reasoning_enabled,
            reasoning_supported=supported,
            reasoning_used=used,
            reasoning_effort=effort,
            reasoning_effort_source=effort_source,
        )
        rendered_length = self._last_user_content_length(messages) if prompt_meta else None
        stream_obj._delta_iter = self._stream_with_usage(
            messages=messages,
            temperature=self._tutor_temperature,
            stream_obj=stream_obj,
            prompt_meta=prompt_meta,
            rendered_length=rendered_length,
            effort_override=reasoning_effort_override if used else None,
            operation=operation or None,
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
        operation: str | None = None,
    ) -> Iterator[str]:
        """Stream text deltas inside an LLM span and capture final usage.

        Uses create_span (not start_span) because this is a generator that
        yields across Starlette's thread-pool boundary.  start_span calls
        tracer.start_as_current_span which attaches a ContextVar token; if the
        generator resumes in a different thread context the subsequent detach
        raises ``ValueError: Token was created in a different Context``.

        ``operation`` explicitly names the span.  When omitted the active
        observation context is consulted, then falls back to ``"llm.stream"``.
        """
        context = get_observation_context()
        op = operation or str(context.get("operation") or "llm.stream")
        span_name = f"llm.{op}" if not op.startswith("llm.") else op
        collected_text: list[str] = []

        span = create_span(
            span_name,
            kind=SPAN_KIND_LLM,
            component="llm",
            operation=op,
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
            llm_system=self._provider,
            llm_provider=self._provider,
        )
        set_prompt_metadata(span, prompt_meta, rendered_length=rendered_length)

        sdk_messages = self._prepare_messages(messages)
        last_chunk: Mapping[str, Any] = {}
        try:
            for chunk in self._sdk_stream_call(
                messages=sdk_messages,
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
        reasoning_content = self._extract_reasoning_content(last_chunk)
        stream_obj.set_usage(
            prompt_tokens=usage.get("token_prompt"),
            completion_tokens=usage.get("token_completion"),
            total_tokens=usage.get("token_total"),
            reasoning_tokens=reasoning_tokens,
            cached_tokens=usage.get("token_cached"),
            reasoning_content=reasoning_content,
        )
        cached = usage.get("token_cached")
        if cached:
            log.debug("prefix cache hit (stream): %d tokens cached", cached)

        response_text = "".join(collected_text)
        set_llm_span_attributes(
            span,
            response_message=response_text,
            token_usage=usage,
        )
        if reasoning_tokens is not None and span is not None:
            span.set_attribute(LLM_TOKEN_COUNT_REASONING, int(reasoning_tokens))
        if reasoning_content is not None and span is not None:
            span.set_attribute(LLM_REASONING_CONTENT, reasoning_content[:256])

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

    @staticmethod
    def _extract_reasoning_content(payload: Mapping[str, Any]) -> str | None:
        """Extract reasoning/thinking text from provider responses.

        Checks two formats:
        - ``choices[0].message.reasoning_content`` (Anthropic/DeepSeek via OpenAI-compat)
        - ``choices[0].message.content`` as list with ``type="thinking"`` blocks (Claude native)
        """
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        message = choices[0].get("message") if isinstance(choices[0], Mapping) else None
        if not isinstance(message, Mapping):
            return None

        # Format 1: top-level reasoning_content field
        rc = message.get("reasoning_content")
        if isinstance(rc, str) and rc.strip():
            return rc

        # Format 2: content blocks with type="thinking"
        content = message.get("content")
        if isinstance(content, list):
            thinking_parts = [
                item.get("thinking", "")
                for item in content
                if isinstance(item, Mapping) and item.get("type") == "thinking"
            ]
            combined = "".join(thinking_parts)
            if combined.strip():
                return combined

        return None

    @staticmethod
    def _is_format_error(exc: Exception) -> bool:
        """Return True if *exc* indicates an unsupported response_format."""
        cause = getattr(exc, "__cause__", None)
        # BadRequestError from litellm/openai SDK (avoid importing the package)
        if cause is not None and type(cause).__name__ == "BadRequestError":
            return True
        for e in (exc, cause):
            if e is None:
                continue
            msg = str(e).lower()
            if "response_format" in msg:
                return True
            if "format type" in msg and "unavailable" in msg:
                return True
            if "json_schema" in msg and (
                "not supported" in msg or "unavailable" in msg
            ):
                return True
        return False

    def _chat_json(
        self,
        *,
        schema_name: str,
        schema: dict[str, object],
        prompt: str,
        prompt_meta: Any | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """.. deprecated:: Use complete_messages_json() instead."""
        warnings.warn(
            "_chat_json is deprecated, use complete_messages_json instead",
            DeprecationWarning,
            stacklevel=2,
        )
        base_system = system_prompt or "Return only JSON that satisfies the provided schema."
        messages = MessageBuilder().system(base_system).user(prompt).build()
        return self.complete_messages_json(
            messages,
            schema_name=schema_name,
            schema=schema,
            prompt_meta=prompt_meta,
        )

    def complete_messages_json(
        self,
        messages: list[Message],
        *,
        schema_name: str,
        schema: dict[str, object],
        prompt_meta: Any | None = None,
    ) -> dict[str, Any]:
        """JSON-mode LLM call from pre-built messages with format fallback.

        This is the ``messages[]``-native entry point for structured JSON
        calls.  ``_chat_json`` delegates here after constructing a simple
        two-message list.
        """
        schema_hint = json.dumps(schema, indent=2)
        schema_suffix = (
            f"\n\nYou MUST respond with a JSON object conforming to this schema:\n"
            f"```json\n{schema_hint}\n```"
        )

        if self._model_supports_json_schema():
            attempts: list[tuple[dict[str, object] | None, bool, str]] = [
                (
                    {
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema_name,
                            "strict": True,
                            "schema": schema,
                        },
                    },
                    False,
                    "json_schema",
                ),
                ({"type": "json_object"}, True, "json_object+hint"),
                (None, True, "prompt-only"),
            ]
        else:
            attempts = [
                ({"type": "json_object"}, True, "json_object+hint"),
                (None, True, "prompt-only"),
            ]

        rendered_length = self._last_user_content_length(messages) if prompt_meta else None

        for i, (response_format, needs_hint, level) in enumerate(attempts):
            attempt_messages = (
                self._with_schema_hint(messages, schema_suffix) if needs_hint
                else list(messages)
            )
            try:
                result = self._call_with_observability(
                    messages=attempt_messages,
                    temperature=self._json_temperature,
                    response_format=response_format,
                    prompt_meta=prompt_meta,
                    rendered_length=rendered_length,
                )
            except Exception as exc:
                if i < len(attempts) - 1 and self._is_format_error(exc):
                    log.warning(
                        "JSON format level '%s' failed for model %s; "
                        "falling back. Error: %s",
                        level,
                        self._model,
                        exc,
                    )
                    continue
                raise
            try:
                content = self._extract_content(result)
                response_payload = json.loads(content)
                if not isinstance(response_payload, dict):
                    raise ValueError("Graph LLM response payload must decode to an object")
                return response_payload
            except (json.JSONDecodeError, ValueError) as parse_exc:
                if i < len(attempts) - 1:
                    log.warning(
                        "JSON parse failed at level '%s' for model %s; "
                        "falling back. Error: %s",
                        level,
                        self._model,
                        parse_exc,
                    )
                    continue
                raise

        raise RuntimeError(
            f"All JSON format attempts exhausted for model {self._model}"
        )

    def _chat_text(self, *, prompt: str, system_instruction: str) -> str:
        """.. deprecated:: Use complete_messages() instead."""
        warnings.warn(
            "_chat_text is deprecated, use complete_messages instead",
            DeprecationWarning,
            stacklevel=2,
        )
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

        .. deprecated:: Use complete_messages() instead.

        ``reasoning_effort_override`` is a reserved seam for future first-layer
        per-call effort selection.
        """
        warnings.warn(
            "_chat_text_traced is deprecated, use complete_messages instead",
            DeprecationWarning,
            stacklevel=2,
        )
        messages: list[Message] = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ]
        return self.complete_messages(
            messages,
            prompt_meta=prompt_meta,
            reasoning_effort_override=reasoning_effort_override,
        )

    def complete_messages(
        self,
        messages: list[Message],
        *,
        prompt_meta: Any | None = None,
        reasoning_effort_override: str | None = None,
    ) -> tuple[str, "GenerationTrace"]:
        """Non-streaming LLM call from pre-built messages.

        This is the ``messages[]``-native entry point for blocking calls.
        ``_chat_text_traced`` delegates here after constructing a simple
        two-message list.
        """
        import time as _time  # noqa: PLC0415

        from core.schemas.assistant import GenerationTrace  # noqa: PLC0415

        rendered_length = self._last_user_content_length(messages) if prompt_meta else None
        t0 = _time.monotonic_ns()
        result = self._call_with_observability(
            messages=messages,
            temperature=self._tutor_temperature,
            response_format=None,
            prompt_meta=prompt_meta,
            rendered_length=rendered_length,
        )
        elapsed_ms = round((_time.monotonic_ns() - t0) / 1_000_000, 2)
        text = self._extract_content(result).strip()
        usage = extract_token_usage(result)
        reasoning = self._extract_reasoning_tokens(result)
        reasoning_content = self._extract_reasoning_content(result)
        supported = self._model_supports_reasoning()
        used = self._reasoning_enabled and supported
        if reasoning_effort_override is not None and used:
            effort = reasoning_effort_override
            effort_source = "override"
        else:
            effort = self._reasoning_effort if used else None
            effort_source = "settings" if effort is not None else None
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
            reasoning_content=reasoning_content,
            cached_tokens=usage.get("token_cached"),
            reasoning_requested=self._reasoning_enabled,
            reasoning_supported=supported,
            reasoning_used=used,
            reasoning_effort=effort,
            reasoning_effort_source=effort_source,
        )
        return text, trace

    @staticmethod
    def _last_user_content_length(messages: list[Message]) -> int | None:
        """Return the length of the last user message's content, or *None*."""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return len(msg.get("content", ""))
        return None

    @staticmethod
    def _with_schema_hint(
        messages: list[Message],
        suffix: str,
    ) -> list[dict[str, str]]:
        """Return a copy of *messages* with *suffix* appended to the first system message."""
        result: list[dict[str, str]] = [dict(m) for m in messages]
        for msg in result:
            if msg.get("role") == "system":
                msg["content"] = msg.get("content", "") + suffix
                return result
        result.insert(0, {"role": "system", "content": suffix.lstrip()})
        return result

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
                llm_system=self._provider,
                llm_provider=self._provider,
            )
            set_prompt_metadata(span, prompt_meta, rendered_length=rendered_length)

            sdk_messages = self._prepare_messages(messages)
            try:
                result = self._sdk_call(
                    messages=sdk_messages,
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
            cached = token_usage.get("token_cached")
            if cached:
                log.debug("prefix cache hit: %d tokens cached", cached)
            reasoning_tokens = self._extract_reasoning_tokens(result)
            reasoning_content = self._extract_reasoning_content(result)
            response_content = self._extract_content_safe(result)

            set_llm_span_attributes(
                span,
                response_message=response_content,
                token_usage=token_usage,
            )
            if reasoning_tokens is not None and span is not None:
                span.set_attribute(LLM_TOKEN_COUNT_REASONING, int(reasoning_tokens))
            if reasoning_content is not None and span is not None:
                span.set_attribute(LLM_REASONING_CONTENT, reasoning_content[:256])
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
        max_retries: int = 2,
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

        self._max_retries = max_retries
        self._client = OpenAI(
            api_key=api_key.strip(),
            timeout=timeout_seconds,
            max_retries=max_retries,
        )

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
        response = get_llm_limiter().execute(self._client.chat.completions.create, **kwargs)
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
        response = get_llm_limiter().execute(self._client.chat.completions.create, **kwargs)
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
        base_url: str | None = None,
        api_key: str | None = None,
        reasoning_enabled: bool = False,
        reasoning_effort: str | None = None,
        num_retries: int = 2,
        context_window_fallback_dict: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            model=model,
            timeout_seconds=timeout_seconds,
            json_temperature=json_temperature,
            tutor_temperature=tutor_temperature,
            provider="litellm",
            reasoning_enabled=reasoning_enabled,
            reasoning_effort=reasoning_effort,
        )
        self._base_url = base_url.rstrip("/") if base_url and base_url.strip() else None
        self._api_key = api_key.strip() if api_key and api_key.strip() else None
        self._num_retries = num_retries
        self._context_window_fallback_dict = context_window_fallback_dict or {}

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
            "timeout": self._timeout_seconds,
            "num_retries": self._num_retries,
        }
        if self._context_window_fallback_dict:
            kwargs["context_window_fallback_dict"] = self._context_window_fallback_dict
        if self._base_url is not None:
            kwargs["api_base"] = self._base_url
        if self._api_key is not None:
            kwargs["api_key"] = self._api_key
        if response_format is not None:
            kwargs["response_format"] = response_format
        response = get_llm_limiter().execute(litellm.completion, **kwargs)
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
            "timeout": self._timeout_seconds,
            "stream": True,
            "stream_options": {"include_usage": True},
            "num_retries": self._num_retries,
        }
        if self._context_window_fallback_dict:
            kwargs["context_window_fallback_dict"] = self._context_window_fallback_dict
        if self._base_url is not None:
            kwargs["api_base"] = self._base_url
        if self._api_key is not None:
            kwargs["api_key"] = self._api_key
        kwargs.update(self._build_reasoning_kwargs(effort_override=effort_override))
        response = get_llm_limiter().execute(litellm.completion, **kwargs)
        for chunk in response:
            yield chunk.model_dump() if hasattr(chunk, "model_dump") else dict(chunk)
