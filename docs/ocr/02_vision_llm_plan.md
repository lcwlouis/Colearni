# OCR2 — Vision LLM Client

Parent: `docs/OCR_MASTER_PLAN.md`

## Purpose

Extend the existing LLM provider abstraction to support multimodal (vision) completions. This adds a `describe_images()` method to the `GraphLLMClient` protocol and implements it for both OpenAI and LiteLLM providers using the standard OpenAI vision message format.

## Slices

### OCR2.1 — Protocol extension

**What:** Add `describe_images()` to `GraphLLMClient` protocol in `core/contracts.py`.

**Steps:**
1. Add method to `GraphLLMClient` protocol:
   ```python
   def describe_images(
       self,
       *,
       images: Sequence[str],
       prompt: str,
       system_prompt: str | None = None,
   ) -> str:
       """Describe visual content in one or more base64-encoded images.
       
       Args:
           images: Base64-encoded PNG strings (no data URI prefix).
           prompt: User prompt describing what to extract.
           system_prompt: Optional system prompt.
       
       Returns:
           LLM-generated description of the visual content.
       """
       ...
   ```
2. Add `from collections.abc import Sequence` import if not present
3. Update `MockGraphLLMClient` (if it exists) with a stub implementation

**Exit criteria:**
- Protocol has `describe_images` method with correct signature
- Existing protocol methods unchanged
- Mock client updated

---

### OCR2.2 — Vision settings

**What:** Add vision-related settings to `core/settings.py`.

**Steps:**
1. Add to the settings class:
   ```python
   # --- Vision extraction (PDF) ---
   ingest_vision_enabled: bool = False
   vision_llm_model: str = "gpt-4o-mini"
   vision_llm_provider: str | None = None  # falls back to graph_llm_provider
   vision_llm_timeout_seconds: float = 60.0
   vision_max_pages_per_call: int = 4
   vision_max_pages_per_document: int = 50
   vision_render_dpi: int = 150
   vision_text_threshold: int = 100  # chars/page below which page is "visual_only"
   ```
2. All settings prefixed with `APP_` env var convention (verify existing pattern)

**Exit criteria:**
- All settings have safe defaults (vision disabled by default)
- Settings are accessible via the existing settings pattern
- No existing settings changed

---

### OCR2.3 — Multimodal message builder

**What:** Add `_chat_vision()` to `_BaseGraphLLMClient` in `adapters/llm/providers.py`.

**Steps:**
1. Implement `_chat_vision()` method:
   ```python
   def _chat_vision(
       self,
       *,
       images: Sequence[str],
       prompt: str,
       system_prompt: str | None = None,
   ) -> tuple[str, dict[str, Any]]:
       """Build and execute a vision completion call.
       
       Returns (response_text, usage_dict).
       """
       content_blocks: list[dict[str, Any]] = [
           {"type": "text", "text": prompt},
       ]
       for img_b64 in images:
           content_blocks.append({
               "type": "image_url",
               "image_url": {
                   "url": f"data:image/png;base64,{img_b64}",
                   "detail": "high",
               },
           })
       
       messages: list[dict[str, Any]] = []
       if system_prompt:
           messages.append({"role": "system", "content": system_prompt})
       messages.append({"role": "user", "content": content_blocks})
       
       # Call through existing SDK method (no response_format for vision)
       return self._sdk_call(
           model=self._vision_model,
           temperature=0.0,
           messages=messages,
           response_format=None,
       )
   ```
2. Add `_vision_model` property that reads from settings (with fallback to graph model)
3. Wrap with observability span (`openinference.span.kind = "LLM"`)

**Exit criteria:**
- Message format matches OpenAI vision API spec
- Multiple images supported in single call
- Temperature fixed at 0.0 for deterministic extraction
- No `response_format` sent (vision calls don't support json_schema)

---

### OCR2.4 — Provider implementations

**What:** Implement `describe_images()` in both `OpenAIGraphLLMClient` and `LiteLLMGraphLLMClient`.

**Steps:**
1. In both providers, implement `describe_images()`:
   ```python
   def describe_images(
       self,
       *,
       images: Sequence[str],
       prompt: str,
       system_prompt: str | None = None,
   ) -> str:
       if not images:
           return ""
       
       with self._start_vision_span(image_count=len(images)) as span:
           text, usage = self._chat_vision(
               images=images,
               prompt=prompt,
               system_prompt=system_prompt,
           )
           self._record_usage(span, usage)
           return text
   ```
2. Add `_start_vision_span()` helper using existing observability patterns
3. Ensure token usage is tracked (for cost monitoring)
4. Use vision-specific model and timeout settings

**Exit criteria:**
- Both providers produce identical behavior for `describe_images()`
- Token usage tracked in spans
- Empty image list returns empty string without API call
- API errors propagated with clear messages

## Audit Workspace

(Initially empty — populated during self-audit phase)
