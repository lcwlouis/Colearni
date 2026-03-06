# OCR4 — Testing

Parent: `docs/OCR_MASTER_PLAN.md`

## Purpose

Comprehensive test coverage for all vision extraction functionality, covering unit tests, integration tests, and edge cases.

## Dependencies

- `OCR3` (Extraction Pipeline) — integration tests require the full pipeline

## Slices

### OCR4.1 — pdf_vision.py unit tests

**What:** Unit tests for image detection, page rendering, and classification.

**File:** `tests/parsers/test_pdf_vision.py`

**Test cases:**
1. `test_detect_visual_pages_text_only_pdf` — text-native PDF returns 0 image counts per page
2. `test_detect_visual_pages_with_images` — PDF with embedded image returns image_count > 0
3. `test_detect_visual_pages_empty_pdf` — 0-page PDF returns empty list
4. `test_render_pages_to_images_valid` — renders page to valid base64 PNG, width/height > 0
5. `test_render_pages_to_images_out_of_range` — out-of-range index skipped (no crash)
6. `test_render_pages_to_images_custom_dpi` — higher DPI produces larger image
7. `test_classify_pages_text_only` — page with 500+ chars and no images → TEXT_ONLY
8. `test_classify_pages_mixed` — page with 500+ chars and images → MIXED
9. `test_classify_pages_visual_only` — page with < 100 chars → VISUAL_ONLY
10. `test_classify_pages_visual_indices` — visual_page_indices contains mixed + visual_only
11. `test_classify_pages_custom_threshold` — custom text_threshold respected

**Fixtures:** Create minimal PDFs using `pypdf` or `reportlab` for test data.

**Exit criteria:**
- All 11 test cases pass
- Tests use real (tiny) PDFs, not mocks of internal pypdf state
- Edge cases covered: empty PDF, single page, multi-page

---

### OCR4.2 — Vision LLM client unit tests

**What:** Unit tests for multimodal message building and describe_images.

**File:** `tests/llm/test_vision_client.py`

**Test cases:**
1. `test_chat_vision_message_format` — verify message structure matches OpenAI vision spec
2. `test_chat_vision_single_image` — one image produces one image_url block
3. `test_chat_vision_multiple_images` — N images produce N image_url blocks
4. `test_chat_vision_with_system_prompt` — system message prepended when provided
5. `test_chat_vision_without_system_prompt` — no system message when None
6. `test_describe_images_empty_list` — returns empty string without API call
7. `test_describe_images_calls_api` — mock SDK call, verify response returned
8. `test_describe_images_tracks_usage` — verify observability span created with token counts
9. `test_describe_images_api_error` — API errors propagated clearly

**Approach:** Mock the underlying SDK call (`self._client.chat.completions.create` / `litellm.completion`) to avoid real API calls.

**Exit criteria:**
- Message format exactly matches OpenAI multimodal spec
- Data URI format is `data:image/png;base64,{b64string}`
- Empty images handled without API call
- Error propagation tested

---

### OCR4.3 — Extraction pipeline unit tests

**What:** Unit tests for the orchestration logic, batching, and text merging.

**File:** `tests/ingestion/test_vision_extraction.py`

**Test cases:**
1. `test_extract_visual_pages_no_visual_content` — all text-only pages → empty dict
2. `test_extract_visual_pages_single_visual_page` — one visual page → dict with one entry
3. `test_extract_visual_pages_batching` — 7 pages with batch size 4 → 2 batches (4 + 3)
4. `test_extract_visual_pages_max_pages_cap` — 60 visual pages with cap of 50 → only 50 processed
5. `test_split_batch_response_single_page` — no markers → whole response for the page
6. `test_split_batch_response_multi_page` — "--- Page N ---" markers correctly split
7. `test_split_batch_response_malformed` — no markers in multi-page → fallback to first page
8. `test_extract_pdf_text_no_vision` — vision_texts=None → identical to current behavior
9. `test_extract_pdf_text_mixed_page` — pypdf text + vision text merged with separator
10. `test_extract_pdf_text_visual_only_page` — empty pypdf text replaced by vision text
11. `test_extract_pdf_text_text_only_page_with_vision_dict` — page not in vision_texts → unchanged

**Approach:** Mock `classify_pages`, `render_pages_to_images`, and `llm_client.describe_images`.

**Exit criteria:**
- Batching arithmetic is correct (ceiling division)
- Max page cap enforced
- Text merging produces expected output for all three page types
- Backward compatibility verified (no vision = no change)

---

### OCR4.4 — Integration test

**What:** End-to-end test with a real PDF (but mocked LLM).

**File:** `tests/ingestion/test_vision_integration.py`

**Test cases:**
1. `test_vision_ingestion_end_to_end` — PDF with text + image page → ingested with vision content in chunks
2. `test_vision_disabled_no_change` — same PDF with vision disabled → identical to non-vision ingestion
3. `test_vision_non_pdf_skipped` — .txt file with vision enabled → no vision processing
4. `test_vision_llm_unavailable_graceful` — vision enabled but no LLM client → warning logged, ingestion proceeds with pypdf only

**Approach:** Use the existing ingestion test patterns from `tests/core/test_ingestion_pdf.py`.

**Exit criteria:**
- End-to-end flow produces chunks containing `[Visual Content]` markers
- Disabled path produces identical output to current behavior
- Non-PDF files unaffected
- Missing LLM client doesn't crash ingestion

## Audit Workspace

(Initially empty — populated during self-audit phase)
