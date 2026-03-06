# OCR3 — Extraction Pipeline

Parent: `docs/OCR_MASTER_PLAN.md`

## Purpose

Wire the two-tier extraction into the ingestion pipeline. This is the integration track that brings page classification (OCR1) and vision LLM (OCR2) together with carefully crafted prompts and page batching.

## Dependencies

- `OCR1` (Page Analysis Infrastructure) — uses `classify_pages()`, `render_pages_to_images()`
- `OCR2` (Vision LLM Client) — uses `describe_images()`

## Slices

### OCR3.1 — Vision extraction prompt assets

**What:** Create prompt templates for vision-based page content extraction.

**Steps:**
1. Create system prompt asset `prompts/vision_extract_page_v1_system.md`:
   ```
   You are a precise document content extractor for an educational learning
   platform called Colearni. Your extracted content will be used to build a
   knowledge graph of learning concepts and to tutor students.

   Core principles:
   - Extract ONLY what is visible on the page — never infer or add external knowledge.
   - Preserve the structure and relationships between elements (headings, lists, tables).
   - Visual elements (diagrams, charts, figures) must be described in enough detail
     that a student who cannot see the image could still learn the same concepts.
   - Accuracy is paramount: a wrong transcription is worse than a missing one.
   ```

2. Create user prompt asset `prompts/vision_extract_page_v1.md`:
   ```
   Extract ALL meaningful content from the PDF page image(s) below.
   A student will rely on your output to study this material without
   access to the original document.

   ## How to Extract Each Content Type

   ### Text and Headings
   - Reproduce all visible text faithfully in reading order.
   - Format headings with markdown (#, ##, ###).
   - Preserve lists (bulleted and numbered) with markdown syntax.
   - Keep paragraph breaks where they appear in the original.

   ### Tables
   - Use markdown table syntax with | column | headers |.
   - Include ALL rows and columns — do not summarize or truncate.
   - If a table is cut off at a page boundary, note: "[Table continues on next page]"
   - For complex merged cells, use the closest markdown approximation and add
     a note explaining the structure.

   ### Diagrams and Flowcharts
   - Begin with: **[DIAGRAM: <specific type>]** (e.g., flowchart, UML class diagram,
     network topology, process diagram, Venn diagram, concept map)
   - **Nodes/Elements**: List every labeled box, circle, or shape with its exact text.
   - **Connections**: Describe each arrow/line as: "<source> → <target>" with any label.
   - **Flow direction**: State whether the flow is top-to-bottom, left-to-right, or cyclic.
   - **Decision points**: For flowcharts, express as:
     "Decision: <condition> → Yes: <path> | No: <path>"
   - **Groupings**: Note any visual groupings (dashed boxes, swim lanes, color coding).
   - End with a one-sentence summary: "This diagram shows <what it illustrates>."

   ### Charts and Data Visualizations
   - Begin with: **[CHART: <specific type>]** (e.g., bar chart, line graph, pie chart,
     scatter plot, histogram, box plot)
   - **Title**: State the chart title.
   - **Axes**: Label each axis with name and units (e.g., "X-axis: Year (2010-2024)").
   - **Data series**: List each series/category with its key data points.
   - **Trends**: Note significant patterns (increasing, decreasing, peaks, outliers).
   - **Legend**: Reproduce the legend if present.
   - For pie charts: list every segment as "Label: XX%".
   - End with: "Key takeaway: <one sentence describing the main finding>."

   ### Mathematical Content
   - Reproduce equations in LaTeX: $E = mc^2$
   - For multi-line derivations, preserve each step on its own line.
   - Include any variable definitions (e.g., "where m = mass in kg").
   - Note equation numbers if present (e.g., "Equation 3.2").

   ### Photographs and Illustrations
   - Begin with: **[FIGURE <number if present>: <brief description>]**
   - Describe what the image depicts and what it teaches.
   - Include any labels, annotations, or callouts visible in the image.
   - Reproduce the caption if one exists below/above the figure.
   - For scientific images (microscopy, x-rays, etc.): describe observable features.

   ### Code Snippets
   - Reproduce code in fenced code blocks with the language specified:
     ```python
     def example():
         pass
     ```
   - Preserve indentation and line numbers if visible.

   ## What to SKIP
   - Page numbers, running headers/footers
   - Watermarks, publisher logos, copyright notices
   - Decorative borders or background patterns
   - ISBN numbers, printing information

   ## Multi-Page Instructions
   {{#if multi_page}}
   The images below are {{page_count}} consecutive pages from the same document.
   Extract each page's content separately, prefixed with:

   --- Page {{page_numbers}} ---

   Maintain context across pages (e.g., if a table starts on one page and continues
   on the next, note this at both the end of the first page and start of the second).
   {{/if}}

   ## Edge Cases
   - If a page is entirely blank or decorative: respond with only "[BLANK PAGE]"
   - If text is partially obscured or illegible: use "[illegible]" for unclear portions
   - If you are uncertain about a specific word or number: use "[?word?]" notation
   ```

3. Register both prompts in the prompt registry (follow existing patterns for asset loading)

**Exit criteria:**
- Both prompt files exist and load via `PromptRegistry`
- `{{#if multi_page}}` / `{{page_count}}` / `{{page_numbers}}` template variables render correctly
- Prompts cover all content types: text, tables, diagrams, charts, math, figures, code
- Clear instructions for what to skip and how to handle edge cases

---

### OCR3.2 — Vision extraction orchestrator

**What:** Create `domain/ingestion/vision_extraction.py` with the two-tier extraction logic.

**Steps:**
1. Implement main function:
   ```python
   async def extract_visual_pages(
       *,
       raw_bytes: bytes,
       llm_client: GraphLLMClient,
       settings: Settings,
   ) -> dict[int, str]:
       """Extract text from visual PDF pages using a vision LLM.
       
       Returns:
           Mapping of page_index → vision-extracted text for pages
           that contain visual content. Pages not in the result
           should use pypdf text only.
       """
   ```

2. Implementation flow:
   ```
   a. classify_pages(raw_bytes, text_threshold=settings.vision_text_threshold)
   b. Filter to visual_page_indices
   c. Cap at settings.vision_max_pages_per_document (log warning if truncated)
   d. Group into batches of settings.vision_max_pages_per_call
   e. For each batch:
      - render_pages_to_images(raw_bytes, batch_indices, dpi=settings.vision_render_dpi)
      - Build prompt with multi_page=True if batch size > 1
      - Call llm_client.describe_images(images=[...], prompt=..., system_prompt=...)
      - Parse response to split per-page content (via "--- Page N ---" markers)
   f. Return {page_index: extracted_text} for all processed pages
   ```

3. Add helper `_split_batch_response(response: str, page_indices: list[int]) -> dict[int, str]`:
   - Parse "--- Page N ---" markers from LLM response
   - Handle single-page batches (no markers needed)
   - Handle malformed responses (assign entire response to first page)

4. Add helper `_build_vision_prompt(page_indices: list[int], registry: PromptRegistry) -> tuple[str, str]`:
   - Load prompt from registry
   - Render with `multi_page` and `page_numbers` context
   - Return (system_prompt, user_prompt)

5. Wrap entire function with observability span

**Exit criteria:**
- Respects `vision_max_pages_per_document` cap
- Batching groups pages correctly (handles remainders)
- Single-page and multi-page batches both work
- Malformed LLM responses handled gracefully
- Returns empty dict when no visual pages detected

---

### OCR3.3 — Modify text extraction for vision merge

**What:** Extend `_extract_pdf_text()` in `adapters/parsers/text.py` to merge vision-extracted content.

**Steps:**
1. Add optional parameter to `_extract_pdf_text()`:
   ```python
   def _extract_pdf_text(
       raw_bytes: bytes,
       *,
       vision_texts: dict[int, str] | None = None,
   ) -> str:
   ```

2. Modify the per-page loop:
   ```python
   for i, page in enumerate(reader.pages):
       pypdf_text = page.extract_text() or ""
       page_texts.append(pypdf_text)
       
       if vision_texts and i in vision_texts:
           vision_content = vision_texts[i]
           if pypdf_text.strip():
               # Mixed page: append vision content after pypdf text
               page_texts.append(f"\n\n[Visual Content]\n{vision_content}")
           else:
               # Visual-only page: replace with vision content
               page_texts[-1] = vision_content
   ```

3. Update `parse_text_payload()` to accept and pass through `vision_texts`

**Exit criteria:**
- When `vision_texts` is None: behavior identical to current (zero regression)
- Mixed pages: pypdf text + `\n\n[Visual Content]\n` + vision text
- Visual-only pages: vision text replaces empty pypdf text
- Text-only pages (not in vision_texts): unchanged

---

### OCR3.4 — Wire into ingestion service

**What:** Integrate vision extraction into the ingestion pipeline.

**Steps:**
1. In `domain/ingestion/service.py`, modify `ingest_text_document()`:
   ```python
   vision_texts: dict[int, str] | None = None
   if settings.ingest_vision_enabled and mime == "application/pdf":
       vision_texts = await extract_visual_pages(
           raw_bytes=raw_bytes,
           llm_client=llm_client,
           settings=settings,
       )
   
   text, content_hash = parse_text_payload(
       ...,
       vision_texts=vision_texts,
   )
   ```

2. Similarly modify `ingest_text_document_fast()` — note: this path may not have an LLM client available. In that case, vision extraction is skipped even if enabled.

3. Ensure the LLM client is available in the ingestion context (may need to pass it through or resolve it)

4. Add structured logging:
   - Log number of visual pages detected
   - Log number of pages sent to vision LLM
   - Log total vision LLM tokens used

**Exit criteria:**
- Vision extraction runs only when `ingest_vision_enabled=True` AND file is PDF
- When disabled: zero code path change, zero performance impact
- When LLM client unavailable: graceful skip with warning log
- Structured logging for monitoring and cost tracking

## Audit Workspace

(Initially empty — populated during self-audit phase)
