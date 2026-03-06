# Vision-Enhanced PDF Extraction — Master Plan

Last updated: 2026-03-05

Archive snapshots:
- `none`

Template usage:
- This is the cross-track execution plan for adding vision-based PDF page extraction to Colearni's ingestion pipeline.
- It does not replace any existing plans.
- All child plans are subordinate to this document.

## Plan Completeness Checklist

This plan should be treated as incomplete unless it includes:

1. ✅ archive snapshot path(s)
2. ✅ current verification status
3. ✅ ordered track list with stable IDs
4. ✅ verification block template
5. ✅ removal entry template
6. ✅ final section named `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`

## Non-Negotiable Run Rules

1. You MUST re-open and re-read this file:
   - at the start of the run
   - after every 2 refactor slices
   - after any context compaction / summarization / "I may lose context" moment
   - before claiming any slice complete
2. Do not overclaim. A slice is ONLY complete if:
   - code or docs for that slice are changed
   - behavior is verified
   - the slice-specific verification gates in the child plan are met
3. Work in SMALL PR-sized chunks:
   - one slice or sub-slice at a time
   - prefer commit message format: `chore(refactor): <slice-id> <short description>`
4. For each slice, you MUST produce a `Verification Block` (see template below).
5. Do not reopen completed slices unless:
   - the current slice is blocked by them, or
   - the code no longer matches the assumptions in this file
6. If implementation uncovers a behavior change risk, STOP and update this plan before widening scope.
7. Vision extraction must not break existing text-only PDF ingestion.
8. A generated refactor plan is INCOMPLETE unless it ends with a section titled:
   - `## REQUIRED KICKOFF PROMPT (DO NOT OMIT)`
   - followed by exactly one fenced code block containing the run prompt

## Purpose

Colearni's current PDF ingestion pipeline uses `pypdf` to extract text from born-digital PDFs. This works well for text-native documents but silently loses content from:
- **Mixed-content pages**: text alongside diagrams, charts, flowcharts, or embedded images
- **Scanned documents**: image-based PDFs with no extractable text layer
- **Visually-structured content**: tables, formatted layouts, mathematical notation in images

The current code in `adapters/parsers/text.py` already detects likely image-based PDFs (average < 100 chars/page) and logs a warning, but takes no corrective action. Diagrams on pages with sufficient text are entirely invisible.

This plan adds a **two-tier extraction system**: pypdf for text, with automatic detection of pages containing visual content (images, diagrams, charts) and selective use of a vision-capable LLM to extract and describe that visual content. Pages are batched to minimize API cost.

## Inputs Used

This plan is based on:

- Current `adapters/parsers/text.py` (pypdf text extraction, image-detection warning)
- Current `adapters/llm/providers.py` (OpenAI + LiteLLM client abstractions)
- Current `core/contracts.py` (`GraphLLMClient` protocol)
- Current `core/settings.py` (model + ingestion configuration)
- Current `domain/ingestion/service.py` and `post_ingest.py` (ingestion pipeline)
- Current `adapters/parsers/chunker.py` (deterministic chunking)
- `pyproject.toml` dependencies: `pypdf>=6,<7`, `litellm>=1.81,<2`, `openai>=1.30,<3`
- OpenAI Vision API message format (multimodal content blocks)
- PyMuPDF (pymupdf) documentation for page-to-image rendering

## Executive Summary

What is already in good shape:
- Text extraction from born-digital PDFs via pypdf
- Deterministic chunking with word/char overlap
- LLM provider abstraction (OpenAI + LiteLLM) with observability
- Prompt registry with asset loading and rendering
- Image-based PDF detection (avg chars/page < 100 heuristic)
- Full ingestion pipeline with embeddings, summarization, and graph extraction

What is critically broken or materially missing:
1. **No image/diagram detection at page level** — only aggregate average chars/page check
2. **No page-to-image rendering** — no PyMuPDF or equivalent dependency
3. **No vision/multimodal LLM support** — message format is text-only
4. **No vision extraction prompts** — no prompts for describing visual content
5. **No batching for vision calls** — no mechanism to group pages into single LLM calls
6. **Scanned PDFs produce empty or junk text** — no fallback path

## Non-Negotiable Constraints

1. Existing text-only PDF ingestion must continue to work identically (zero regression)
2. Vision extraction is opt-in via settings (disabled by default) — users without vision model access must not be affected
3. PRs ≤ 400 LOC net; split if larger
4. All new behavior requires pytest coverage
5. Vision LLM calls must respect existing observability patterns (spans, token tracking)
6. No unbounded loops — batch sizes and page counts must be capped
7. Must work with both OpenAI and LiteLLM providers

## Completed Work (Do Not Reopen Unless Blocked)

- pypdf text extraction (`adapters/parsers/text.py`)
- Deterministic chunking (`adapters/parsers/chunker.py`)
- LLM provider abstraction (`adapters/llm/providers.py`)
- Prompt registry (`core/prompting/registry.py`)
- Ingestion pipeline (`domain/ingestion/service.py`, `post_ingest.py`)

## Remaining Track IDs

- `OCR1` Page Analysis Infrastructure — PyMuPDF dependency, image detection, page rendering
- `OCR2` Vision LLM Client — Multimodal message support for OpenAI + LiteLLM
- `OCR3` Extraction Pipeline — Two-tier logic, prompt engineering, batching, wiring
- `OCR4` Testing — Unit, integration, and edge-case test coverage

## Child Plan Map

| Track | Child Plan | Status |
|---|---|---|
| `OCR1` Page Analysis Infrastructure | `docs/ocr/01_page_analysis_plan.md` | pending |
| `OCR2` Vision LLM Client | `docs/ocr/02_vision_llm_plan.md` | pending |
| `OCR3` Extraction Pipeline | `docs/ocr/03_extraction_pipeline_plan.md` | pending |
| `OCR4` Testing | `docs/ocr/04_testing_plan.md` | pending |

## Decision Log

1. **PyMuPDF over pdf2image**: PyMuPDF (`pymupdf`) renders pages to images natively without requiring system-level poppler installation. It's faster and has better Python-native support. `pdf2image` requires `poppler-utils` OS package which complicates deployment.
2. **Vision LLM over traditional OCR**: Traditional OCR (Tesseract, EasyOCR, PaddleOCR) extracts flat text — tables become word soup, diagrams yield scattered labels with no structure. A vision LLM understands layout, relationships, and can describe visual content in natural language suitable for knowledge graph extraction. Colearni already has LLM infrastructure.
3. **Two-tier over blanket vision**: Running every page through a vision LLM is wasteful and slow. Most PDF pages are text-native and pypdf handles them perfectly. Vision is reserved for pages with detected images/visual content or insufficient extracted text.
4. **Page-level detection via XObject inspection**: pypdf can enumerate embedded images via page resource XObjects without any API call. This is the cheapest possible signal for "this page has visual content."
5. **Opt-in via settings**: Vision extraction adds latency and cost. It must be disabled by default and enabled per-deployment via `APP_INGEST_VISION_ENABLED=true`.
6. **Batching pages per vision call**: Vision models support multi-image inputs. Batching 4–8 pages per call reduces round-trips and per-call overhead while keeping context window manageable.
7. **Output appended, not replaced**: For mixed-content pages, vision-extracted content is appended to pypdf-extracted text (after deduplication), not substituted. This preserves high-fidelity text extraction while adding visual descriptions.

## Clarifications Requested (Already Answered)

1. *Should we use a small OCR model as a middle tier?* → No. Traditional OCR doesn't understand structure (tables, diagrams). The cost savings don't justify the added complexity for Colearni's use case. Two tiers (pypdf + vision LLM) is simpler and more effective.
2. *What about pages with text AND diagrams?* → Detect via XObject image inspection. Pages with embedded images get vision processing regardless of text extraction success. Vision output is appended to pypdf text.

## Deferred Follow-On Scope

- **PDF table extraction libraries** (camelot, tabula): Vision LLM handles tables well enough; dedicated libraries add complexity
- **Incremental page re-processing**: Re-extracting individual pages from already-ingested documents
- **Vision model fine-tuning**: Using Colearni-specific training data to improve extraction quality
- **Non-PDF visual formats**: PowerPoint, DOCX with embedded images, HTML with screenshots
- **Cost estimation UI**: Showing users estimated vision API cost before ingestion

## Removal Safety Rules

These rules apply whenever a remaining slice removes, replaces, inlines, or archives code:

1. Do not remove a file, function, route, schema, type, selector, or compatibility shim without recording:
   - what is being removed
   - why removal is safe
   - what replaces it
   - how to restore it if rollback is needed
2. Prefer staged removal over hard deletion.
3. Maintain a removal ledger in each child plan during the run.

## Removal Entry Template

```text
Removal Entry - <slice-id>

Removed artifact
- <file / function / route / schema / selector>

Reason for removal
- <why it was dead, duplicated, or replaced>

Replacement
- <new file/module/path or "none" if true deletion>

Reverse path
- <exact steps to restore or revert>

Compatibility impact
- <public/internal, none/minor/major>

Verification
- <tests or manual checks proving the replacement works>
```

## Current Verification Status

Current repo verification status:

- `pytest -q`: baseline (to be captured at start of implementation)
- `ruff check .`: baseline (to be captured at start of implementation)

Current remaining hotspots:

| File | Why it still matters |
|---|---|
| `adapters/parsers/text.py` | Core file being extended — must not regress text extraction |
| `adapters/llm/providers.py` | Adding vision method — must not break existing LLM calls |
| `core/contracts.py` | Protocol extension — must remain backward-compatible |
| `core/settings.py` | New settings — must have safe defaults |

## Remaining Work Overview

### OCR1. Page Analysis Infrastructure

Add the foundation for detecting and rendering visual content from PDF pages. This track introduces the PyMuPDF dependency for high-quality page-to-image rendering, implements per-page image detection via pypdf's XObject resource inspection, and creates a utility module (`adapters/parsers/pdf_vision.py`) that renders selected pages to base64-encoded PNG images suitable for vision LLM input.

**Slices:**
- `OCR1.1` Add `pymupdf` dependency to `pyproject.toml`, verify installation
- `OCR1.2` Create `adapters/parsers/pdf_vision.py` with:
  - `detect_visual_pages(pdf_bytes) → list[PageVisualInfo]`: inspect each page's XObjects for embedded images, return page indices + image counts
  - `render_pages_to_images(pdf_bytes, page_indices, dpi=150) → list[PageImage]`: render specified pages to base64 PNG via PyMuPDF
  - Dataclasses: `PageVisualInfo(page_index, image_count, has_text)`, `PageImage(page_index, base64_png, width, height)`
- `OCR1.3` Add `classify_pages(pdf_bytes) → PageClassification` that combines pypdf text extraction with XObject detection to classify each page as: `text_only`, `mixed` (text + images), or `visual_only` (scanned/image-based)

### OCR2. Vision LLM Client

Extend the existing LLM provider abstraction to support multimodal (vision) completions. This adds a `describe_images()` method to the `GraphLLMClient` protocol and implements it for both OpenAI and LiteLLM providers using the standard OpenAI vision message format (content blocks with `image_url` type using base64 data URIs).

**Slices:**
- `OCR2.1` Add `describe_images()` to `GraphLLMClient` protocol in `core/contracts.py` with signature: `describe_images(*, images: Sequence[str], prompt: str, system_prompt: str | None = None) → str` where images are base64 PNG strings
- `OCR2.2` Add vision model settings to `core/settings.py`:
  - `ingest_vision_enabled: bool = False`
  - `vision_llm_model: str = "gpt-4o-mini"` (cheap default)
  - `vision_llm_provider: str | None = None` (falls back to graph_llm_provider)
  - `vision_max_pages_per_call: int = 4`
  - `vision_max_pages_per_document: int = 50`
  - `vision_render_dpi: int = 150`
- `OCR2.3` Implement `_chat_vision()` in `_BaseGraphLLMClient` that builds multimodal messages:
  ```python
  messages = [
      {"role": "system", "content": system_prompt},
      {"role": "user", "content": [
          {"type": "text", "text": prompt},
          {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}", "detail": "high"}},
          # ... more images
      ]}
  ]
  ```
- `OCR2.4` Implement `describe_images()` in both `OpenAIGraphLLMClient` and `LiteLLMGraphLLMClient`, wiring through `_chat_vision()` with observability spans and token tracking

### OCR3. Extraction Pipeline

Wire the two-tier extraction into the ingestion pipeline with carefully crafted prompts and page batching. This is the integration track that brings OCR1 and OCR2 together.

**Slices:**
- `OCR3.1` Create vision extraction prompt assets:
  - `prompts/vision_extract_page_v1.md` — single/multi-page extraction prompt
  - `prompts/vision_extract_page_v1_system.md` — system prompt

  **System prompt** (`vision_extract_page_v1_system`):
  ```
  You are a document content extractor for an educational learning platform.
  Your output will be used for knowledge graph construction and student tutoring.
  Extract content faithfully — never add interpretation or external information.
  ```

  **User prompt** (`vision_extract_page_v1`):
  ```
  Extract ALL meaningful content from the following PDF page(s). Your output
  must capture every piece of information a student would need to learn from
  this material.

  ## Extraction Rules

  ### Text
  - Reproduce all visible text preserving paragraph structure and reading order.
  - Use markdown headings (#, ##, ###) for document headings.
  - Use markdown lists (-, 1.) for bulleted/numbered content.

  ### Tables
  - Reproduce tables using markdown table syntax with column headers.
  - Preserve all cell values. If a table spans pages, note "[continues on next page]".

  ### Diagrams and Flowcharts
  - Prefix with **[DIAGRAM: <type>]** (e.g., [DIAGRAM: flowchart], [DIAGRAM: concept map]).
  - List every labeled node, box, or element.
  - Describe all connections/arrows with their labels: "A → B (label)".
  - For flowcharts: describe decision points as "If <condition>: → <path>".
  - For concept maps: list relationships as "<concept> —[relationship]→ <concept>".

  ### Charts and Graphs
  - Prefix with **[CHART: <type>]** (e.g., [CHART: bar chart], [CHART: line graph]).
  - State the chart title, axis labels, and units.
  - List all data series with key data points and notable trends.
  - For pie charts: list all segments with percentages.

  ### Mathematical Content
  - Reproduce equations and formulas in LaTeX: $E = mc^2$
  - Include variable definitions and surrounding context.

  ### Images and Illustrations
  - Prefix with **[FIGURE: <description>]**.
  - Describe what the image teaches or demonstrates.
  - Include figure numbers and captions if present.
  - Skip purely decorative elements (logos, borders, watermarks).

  ### What NOT to Include
  - Page numbers, headers/footers (unless they contain content)
  - Decorative borders, logos, or watermarks
  - Your own commentary, analysis, or interpretation
  - Information not visible on the page

  {{#if multi_page}}
  The images below are consecutive pages. Separate each page's content with:
  --- Page {{page_numbers}} ---
  {{/if}}

  If a page is blank or contains only decorative elements, output: [BLANK PAGE]
  ```

- `OCR3.2` Create `domain/ingestion/vision_extraction.py` with:
  - `extract_visual_pages(pdf_bytes, settings, llm_client) → dict[int, str]`: orchestrates the full two-tier flow:
    1. Call `classify_pages()` to identify `mixed` and `visual_only` pages
    2. Group pages into batches of `vision_max_pages_per_call` size
    3. For each batch, render pages to images and call `llm_client.describe_images()`
    4. Return mapping of `page_index → extracted_vision_text`
  - Respects `vision_max_pages_per_document` cap
  - Includes observability spans for the full extraction

- `OCR3.3` Modify `adapters/parsers/text.py` → `_extract_pdf_text()` to accept an optional `vision_texts: dict[int, str]` parameter:
  - For `text_only` pages: use pypdf text as before (no change)
  - For `mixed` pages: use pypdf text + append vision-extracted content (with `\n\n[Visual Content]\n` separator to avoid duplication)
  - For `visual_only` pages: use vision-extracted text instead of pypdf text
  - When `vision_texts` is None or empty: behavior is identical to current (backward compatible)

- `OCR3.4` Wire vision extraction into `domain/ingestion/service.py`:
  - In `ingest_text_document()` and `ingest_text_document_fast()`: if `settings.ingest_vision_enabled`, call `extract_visual_pages()` before text extraction and pass results through
  - Guard with feature flag check — when disabled, zero code path change

### OCR4. Testing

Comprehensive test coverage for all new functionality, including edge cases.

**Slices:**
- `OCR4.1` Unit tests for `adapters/parsers/pdf_vision.py`:
  - Test `detect_visual_pages()` with text-only PDF, image-containing PDF, and scanned PDF
  - Test `render_pages_to_images()` produces valid base64 PNG
  - Test `classify_pages()` correctly categorizes page types
  - Test DPI and page index boundary handling

- `OCR4.2` Unit tests for vision LLM client:
  - Test `_chat_vision()` builds correct multimodal message format
  - Test `describe_images()` with mocked OpenAI and LiteLLM responses
  - Test observability span creation
  - Test error handling (API errors, empty image list, oversized batches)

- `OCR4.3` Unit tests for extraction pipeline:
  - Test `extract_visual_pages()` with mocked classify + vision calls
  - Test page batching logic (respects batch size, handles remainders)
  - Test `vision_max_pages_per_document` cap
  - Test modified `_extract_pdf_text()` with vision texts (mixed, visual-only, text-only pages)
  - Test backward compatibility (vision_texts=None produces identical output)

- `OCR4.4` Integration test:
  - End-to-end: PDF with mixed content → ingestion → verify chunks contain vision descriptions
  - Test with vision disabled → verify identical behavior to current
  - Test with real (mocked) multi-page PDF with text + figure pages

## Cross-Track Execution Order

Tracks should be executed in this order. Each track's child plan defines its internal slice order.

1. `OCR1` Page Analysis Infrastructure — foundational utilities, no LLM dependency
2. `OCR2` Vision LLM Client — can execute in parallel with OCR1, no dependency between them
3. `OCR3` Extraction Pipeline — depends on both OCR1 and OCR2 (integration layer)
4. `OCR4` Testing — unit tests for OCR1/OCR2 can start in parallel; integration tests depend on OCR3

Dependencies between tracks:

- `OCR3` depends on `OCR1` because it uses page classification and image rendering
- `OCR3` depends on `OCR2` because it calls `describe_images()` on the vision LLM client
- `OCR1` and `OCR2` are independent and can run in parallel
- `OCR4` unit tests for OCR1/OCR2 can run in parallel with OCR3; integration tests depend on OCR3

## Master Status Ledger

| Track | Status | Last note |
|---|---|---|
| `OCR1` Page Analysis Infrastructure | 🔄 pending | Not started |
| `OCR2` Vision LLM Client | 🔄 pending | Not started |
| `OCR3` Extraction Pipeline | 🔄 pending | Blocked by OCR1 + OCR2 |
| `OCR4` Testing | 🔄 pending | Not started |

## Verification Block Template

For every completed slice, include this exact structure in the child plan:

```text
Verification Block - <slice-id>

Root cause
- <what made this area insufficient?>

Files changed
- <file list>

What changed
- <short description of the changes>

Commands run
- <tests / typecheck / lint commands>

Logic review
- <For each changed file: describe what the code actually does, not just
  what you intended. Trace the data flow. Confirm edge cases are handled.
  "Tests pass" is not sufficient — explain WHY the logic is correct.>

Manual verification steps
- <UI/API/dev verification steps>

Observed outcome
- <what was actually observed>
```

## Verification Matrix

Run these commands at the end of every slice unless the slice is docs-only:

```bash
pytest -q
ruff check .
```

## What Not To Do

Do not do the following during this project:

- Do not modify existing text extraction for text-only PDFs — it works correctly
- Do not add blanket OCR (Tesseract/EasyOCR) — vision LLM is the chosen approach
- Do not make vision extraction enabled by default — it must be opt-in
- Do not send pages with no visual content to the vision LLM — waste of cost
- Do not break the `GraphLLMClient` protocol for existing implementations — extend only
- Do not introduce system-level dependencies (poppler, tesseract binary) — use pure Python packages
- Do not process unlimited pages — always respect `vision_max_pages_per_document` cap

## Self-Audit Convergence Protocol

After all implementation tracks reach "done" in the Master Status Ledger, the run enters a self-audit convergence loop. The agent does NOT stop — it automatically audits its own work.

### Why This Exists

Agents working top-to-bottom through a plan commonly miss edge cases, leave subtle regressions, or make assumptions that don't hold once later slices land. **Passing tests do NOT prove correctness.** Tests only check what they were written to check — they miss logic errors, silent data drops, dead code paths, and integration mismatches. This protocol forces a fresh-eyes review that catches what tests cannot.

### Fresh-Eyes Audit Principle

**The auditor must treat every slice as if it has NOT been implemented.** Do not skim Verification Blocks or trust prior claims. Instead:

1. Read the slice requirements (purpose, implementation steps, exit criteria) as if seeing them for the first time.
2. **Before looking at any code**, independently write down in the Audit Workspace:
   - What files should have been created or changed
   - What logic should exist in each file
   - What edge cases and error paths should be handled
   - What the tests should actually verify (not just "tests pass")
3. **Only then** open the actual code and compare against your independent analysis.
4. For every point in your "should-exist" list, verify it truly exists and is correct.
5. **Do not trust test names.** Open each test, read the body, and confirm it actually tests the claimed behavior with meaningful assertions — not just "no exception thrown."

### Convergence Loop

```text
AUDIT_CYCLE = 0
MAX_AUDIT_CYCLES = 3

while AUDIT_CYCLE < MAX_AUDIT_CYCLES:
    AUDIT_CYCLE += 1
    
    1. Re-read docs/OCR_MASTER_PLAN.md and every child plan in order.
    2. For each completed slice, perform the FRESH-EYES AUDIT:
       a. Read the slice definition (purpose, steps, exit criteria).
       b. In the child plan's Audit Workspace, write your independent
          analysis of what SHOULD exist — before looking at any code.
       c. Now open every file listed in the Verification Block.
          Compare actual code against your independent analysis.
       d. For each implementation step in the slice:
          - Is the logic actually correct, or does it just not crash?
          - Are edge cases handled (empty inputs, nulls, boundaries)?
          - Is error handling meaningful (not swallowed or generic)?
          - Does the code do what the slice SAYS it does, or something
            subtly different?
       e. For each test:
          - Read the test body. Does it assert the RIGHT thing?
          - Does it test edge cases, not just the happy path?
          - Could the test pass even if the implementation is wrong?
            (e.g., mocking too much, asserting only status codes)
       f. BEHAVIORAL AUDIT (DO NOT SKIP): Trace the full code path from
          PDF upload → parse → classify pages → vision extraction →
          text merging → chunking → embeddings. Verify no data is dropped.
       g. PROMPT AUDIT: Open the vision extraction prompt and verify:
          - System vs user role assignment is correct
          - Template variables are actually populated (not placeholders)
          - The prompt produces the expected output format
       h. OBSERVABILITY AUDIT: For any slice that touches tracing, verify
          traces show correct data in the expected panels.
       i. Cross-slice integration: does this slice's output still work
          with what later slices built on top of it?
       j. No TODO/FIXME/HACK comments left in changed files.
       k. No dead imports, unused variables, or orphaned test stubs.
    3. Run the full Verification Matrix (all test suites, typecheck, lint).
    4. Produce an Audit Report in the Audit Workspace (template below).
    5. If CONVERGED (0 issues): update Master Status Ledger with
       "✅ audit-passed" and exit the loop.
    6. If NEEDS_REPASS:
       a. Reopen affected slices (set status back to pending in the
          child plan, add "Audit Cycle N" note)
       b. Re-implement the reopened slices from scratch
       c. Continue to next audit cycle
```

### Audit Workspace

Each child plan MUST contain an `## Audit Workspace` section (initially empty). During the audit, the agent writes its fresh-eyes analysis here:

```text
--- Audit Cycle {N} - {slice-id} ---

What SHOULD exist (written BEFORE reading code):
- Files: <expected file changes>
- Logic: <expected logic in each file>
- Edge cases: <expected edge case handling>
- Tests: <what tests should verify>

What ACTUALLY exists (written AFTER reading code):
- Files: <actual file changes — match/mismatch?>
- Logic: <actual logic — correct/incorrect/missing?>
- Edge cases: <handled/missing?>
- Tests: <meaningful assertions or shallow?>

Gaps found:
- <gap 1>
- <gap 2>
- <none if clean>

Verdict: PASS / REOPEN
Reason: <if reopened, explain exactly what's wrong>
```

### Audit Cycle Budget

- **Maximum 3 audit cycles** to prevent unbounded loops.
- If cycle 3 still finds issues, produce a final Audit Report listing all remaining items and mark them as "deferred to manual review".
- The agent MUST NOT enter cycle 4. Instead, it produces a handoff summary for the human reviewer.

### Audit Report Template

```text
Audit Report — Cycle {N}

Slices re-examined: {count}
Full verification matrix: {PASS / FAIL with details}

Fresh-eyes analysis completed: {yes/no for each slice}

Issues found:
1. [{severity}] {slice-id}: {description}
   - File(s): {paths}
   - Expected (from fresh analysis): {what should be true}
   - Actual (from code review): {what was found}
   - Why tests didn't catch it: {explanation}
   - Action: {reopen slice / cosmetic fix / defer}

Verdict: {CONVERGED | NEEDS_REPASS}
Slices reopened: {list or "none"}
```

### What the Audit Checks

| Check | What it catches |
|---|---|
| Fresh-eyes independent analysis | Assumptions baked in from implementation bias |
| Code logic review (not just test results) | Bugs that tests don't cover, dead code, wrong logic |
| Test body inspection | Shallow tests that pass but don't verify behavior |
| Verification Block accuracy | Slice claims that are no longer true |
| Exit criteria still met | Regressions from later slices |
| TODO/FIXME scan | Unfinished work left behind |
| Dead code scan | Imports, variables, stubs that serve no purpose |
| Behavioral trace | Dropped fields, missing kwargs, stubs |
| Prompt review | Bad role assignment, empty variables |
| Observability review | Traces that don't surface in expected panels |

## REQUIRED KICKOFF PROMPT (DO NOT OMIT)

This section is mandatory.

If this plan does not end with this section and the fenced prompt block below, the plan is incomplete and should be fixed before use.

Use this single prompt for the implementation phase:

```text
Read docs/OCR_MASTER_PLAN.md.
Select the first child plan in execution order that still has incomplete slices.
Read that child plan and begin with its current incomplete slice exactly as described.

Execution loop:

1. Work on exactly one sub-slice at a time and keep the change set PR-sized.
2. Preserve all constraints in docs/OCR_MASTER_PLAN.md and the active child plan.
3. Run the slice verification steps before claiming completion.
4. When a slice is complete, update:
   - the active child plan with a Verification Block
   - the active child plan with any Removal Entries added during that slice
   - docs/OCR_MASTER_PLAN.md with the updated status ledger / remaining status note
5. After every 2 completed slices OR if your context is compacted/summarized, re-open docs/OCR_MASTER_PLAN.md and the active child plan and restate which slices remain.
6. If the active child plan still has incomplete slices, continue to the next slice.
7. If the active child plan is complete, go back to docs/OCR_MASTER_PLAN.md, pick the next incomplete child plan in order, and continue.

Stop only if:

- verification fails
- the current repo behavior does not match plan assumptions and the plan must be updated first
- a blocker requires user input or approval
- completing the next slice would force a risky scope expansion

Do NOT stop because one child plan is complete.
Do NOT stop because you updated the session plan, todo list, or status ledger.
The run is only complete when docs/OCR_MASTER_PLAN.md shows no remaining incomplete tracks.

Additional constraints:
- Vision extraction must not break existing text-only PDF ingestion
- Vision extraction is opt-in (disabled by default via settings)
- All new code must follow existing patterns in adapters/ and domain/
- Respect existing observability patterns (create_span, start_span)

START:

Read docs/OCR_MASTER_PLAN.md.
Pick the first incomplete child plan in execution order.
Begin with the current slice in that child plan exactly as described.
Do not proceed beyond the current slice until verified.
Continue once verified, then go back to the start of this prompt for the next slice.
Make sure you re-read docs/OCR_MASTER_PLAN.md before every move to the next child plan. It can be dynamically updated. Check the latest version and continue.

--- SELF-AUDIT PHASE ---

When docs/OCR_MASTER_PLAN.md shows all tracks complete (no remaining incomplete tracks),
do NOT stop. Enter the self-audit convergence loop:

Audit loop (max 3 cycles):

1. Re-read docs/OCR_MASTER_PLAN.md and every child plan.
2. For each completed slice, verify the Verification Block still holds:
   - Files exist and contain the described changes
   - Tests pass (run full Verification Matrix)
   - Exit criteria are still met (no regressions from later slices)
   - No TODO/FIXME/HACK comments left in changed files
3. Check cross-slice integration:
   - Does each slice's output still work with what later slices built?
   - Are there dead imports, unused code, or orphaned tests?
4. Produce an Audit Report (use template from Self-Audit Convergence Protocol section).
5. If CONVERGED (0 issues found): mark all tracks as "audit-passed" in the
   Master Status Ledger. The run is now complete.
6. If NEEDS_REPASS: reopen affected slices, re-implement them with full
   verification, then start the next audit cycle.
7. If this is cycle 3 and issues remain: produce a final handoff report
   listing all remaining items for manual review. The run is complete.

The run is ONLY complete when:
- All tracks show "audit-passed" in the Master Status Ledger, OR
- 3 audit cycles have been exhausted and a handoff report is produced
```
