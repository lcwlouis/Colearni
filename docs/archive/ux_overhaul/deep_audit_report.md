# CoLearni UX Overhaul — Deep Audit Report

**Date:** 2026-03-02  
**Auditor:** External audit (not the implementing agent)  
**Scope:** All 6 tracks (UXF, UXG, UXP, UXT, UXI, UXD)  
**Test baseline:** 963 backend tests passed, 117 frontend tests passed  

---

## Executive Summary

The agent claimed all 6 tracks are "audit-passed". After thorough code-level
inspection, the **infrastructure code is largely real and present**, but
**several critical design issues were missed or misrepresented** by the
self-audit. The self-audit convergence protocol caught surface-level gaps but
failed to evaluate architectural correctness of prompt construction, toggle
placement, and concept initialization.

### Severity Counts

| Severity | Count |
|----------|-------|
| ❌ Critical (broken/wrong behavior) | 3 |
| ⚠️ Significant (design gap / missing feature) | 4 |
| ℹ️ Minor (cosmetic / improvement opportunity) | 3 |

---

## User-Reported Issues — Findings

### Issue 1: Socratic tutor returns hardcoded "Relation" concept

**Verdict: ❌ CONFIRMED — hardcoded, no adaptation**

**Files:** `core/schemas/tutor_state.py:69-86`, `domain/chat/stream.py:362-363`

`init_relation_concept()` is the ONLY initialization path for Socratic state.
It hardcodes:
- `concept = "Relation"`
- `table_name = "Students"`
- `table_columns = ["sid", "name", "major", "gpa"]`
- 3 fixed rows (Alice/Bob/Carol)

The function takes no arguments and has zero logic to adapt to the user's
selected topic. When a user asks about "Database Engine Internals", the tutor
still initializes with the "Relation" concept and Students table.

In `stream.py:362-363`:
```python
if not tutor_state.active:
    tutor_state.init_relation_concept()  # Always "Relation"
```

There is no `init_concept(topic)` or any topic-aware initialization. The
existing Socratic audit (`socratic_tutor_audit.md:154`) acknowledges this as an
MVP limitation but the master plan marks UXT.4 as "audit-passed" without
flagging it as a known limitation.

**Impact:** Socratic interactive mode is usable ONLY for the "Relation" concept
demo. Any other topic receives a mismatched tutor state.

---

### Issue 2: System prompt placed under user role

**Verdict: ❌ CONFIRMED — architectural design issue**

**File:** `adapters/llm/providers.py:202-205`

```python
messages = [
    {"role": "system", "content": "You are a grounded tutor. Follow style instructions exactly and stay concise."},
    {"role": "user", "content": prompt},
]
```

The system message is a tiny 12-word stub: _"You are a grounded tutor. Follow
style instructions exactly and stay concise."_

The actual detailed prompt template (3,384 bytes of Socratic protocol with 10
non-negotiable rules, 7-section response format, state block, evidence,
document summaries, user query) is **entirely stuffed into the `user` role
message** via the `prompt` parameter.

This is visible in Phoenix traces as:
- `[system]` → tiny generic instruction
- `[user]` → massive detailed prompt template with embedded user query

**Why this matters:**
1. **Prefix caching is suboptimal** — OpenAI caches stable system message
   prefixes, but the system message here is trivial while the long stable
   template is in the user message.
2. **Model instruction-following degrades** — models weight system-role
   instructions more heavily than user-role content for behavioral constraints.
3. **Observability is misleading** — Phoenix Info tab shows the prompt as user
   input, not system instructions.

This applies to BOTH `build_full_tutor_prompt_with_meta` (regular tutor) and
`build_socratic_interactive_prompt` (Socratic mode) — both return a single
string that gets placed into `role: user`.

---

### Issue 3: Dev stats toggle is frontend-only (not `.env`)

**Verdict: ⚠️ CONFIRMED — by design, but user wants `.env` control**

**Implementation:** `apps/web/lib/hooks/use-dev-stats.ts` — localStorage key
`colearni:showDevStats`, toggled via checkbox in `global-sidebar.tsx`.

**What was implemented:** UXI.3 implemented exactly what Decision Log #10
specified: _"Frontend-only via localStorage. Backend always includes
`generation_trace`."_

**What the user wants:** A backend `.env` flag like
`APP_SHOW_DEV_STATS=true/false` that controls whether `generation_trace` is
included in API responses at all, not just a frontend display toggle.

**Current state:** Backend ALWAYS includes `generation_trace` in responses.
The frontend just hides/shows it. There is NO backend `.env` flag for this.

---

### Issue 4: Socratic toggle is frontend-only (not `.env`)

**Verdict: ⚠️ CONFIRMED — frontend state only, no `.env` flag**

**File:** `apps/web/app/(app)/tutor/page.tsx:68-76`

```tsx
<button onClick={() => t.setTutorProtocol(!t.tutorProtocol)}>
  {t.tutorProtocol ? "Socratic ✓" : "Socratic"}
</button>
```

The toggle is a React `useState(false)` in `use-tutor-page.ts:26`. It defaults
to OFF and resets on page refresh. There is no `.env` flag, no localStorage
persistence, and no backend configuration.

**Note:** The Socratic passthrough chain IS now wired (UXT.4 fixed it):
- `ChatRespondAPIRequest.tutor_protocol` field exists (line 57)
- Both route handlers forward it (lines 193, 246)
- `stream.py:359` condition checks it correctly

So the plumbing works — the toggle just needs to be backend-configurable per
the user's preference.

---

### Issue 5: Chat interface lacks full markdown rendering

**Verdict: ⚠️ PARTIAL — tables/math/lists work, but NO syntax highlighting**

**File:** `apps/web/components/markdown-content.tsx`

| Feature | Status |
|---------|--------|
| Tables | ✅ Supported (react-markdown default) |
| Code blocks (fenced) | ✅ Rendered as `<pre><code>` |
| Syntax highlighting | ❌ **MISSING** — no `rehype-highlight`, `shiki`, or `prismjs` |
| LaTeX / math | ✅ Full support via `remark-math` + `rehype-katex` |
| Lists (ul/ol) | ✅ Supported |
| Headings | ✅ Supported |
| Blockquotes | ✅ Styled |

Code blocks render as plain monospace text without language-specific coloring.
For a tutor application that teaches programming concepts, this is a meaningful
UX gap.

---

## Track-by-Track Audit

---

### UXF — Critical Fixes (3 slices)

| Slice | Status | Evidence |
|-------|--------|----------|
| UXF.1 Gardener transaction commit | ✅ Works | `db.commit()` added in graph route |
| UXF.2 Wildcard selection highlight | ✅ Works | `setFocusNodeId()` wired to selection |
| UXF.3 Reduce graph flicker | ✅ Works | Subsumed by Sigma.js replacement in UXG |

**Verdict: ✅ PASS** — All 3 slices genuinely complete. No issues found.

---

### UXG — Graph Replacement (13 slices)

| Slice | Status | Evidence |
|-------|--------|----------|
| UXG.1 Core Sigma.js component | ✅ Real | Full `SigmaContainer` + graphology wiring |
| UXG.2 Data binding | ✅ Real | Graph data → graphology node/edge sync |
| UXG.3 Interaction model | ✅ Real | Click, hover, drag, zoom via sigma events |
| UXG.4 Search | ✅ Real | Node search with highlight |
| UXG.5 Visual styling | ✅ Real | Tier-based colors, edge styling |
| UXG.6 Subgraph | ✅ Real | Neighborhood expansion |
| UXG.7 Detail panel wiring | ✅ Real | Node click → detail panel integration |
| UXG.8 Camera controls | ✅ Real | `useSigma()` → animated zoom/pan/rotate |
| UXG.9 Extended layouts | ✅ Real | ForceAtlas2, Force, Circular, Circlepack, Random + Noverlap |
| UXG.10 Loading states | ✅ Real | SVG-animated skeleton + empty state |
| UXG.11 Legend + status bar | ✅ Real | Tier legend with collapse, visible/total counts |
| UXG.12 Settings panel | ✅ Real | Layout options with localStorage persistence |
| UXG.13 Expand/prune | ✅ Real | Subgraph exploration controls |

**Commits verified:** `a7965be` through `b45a0b7` (6 commits for UXG.8-13).

**Layout algorithms:**
- ForceAtlas2: Real `useWorkerLayoutForceAtlas2()` with gravity, scaling, barnesHut params
- Circlepack: Custom concentric ring implementation grouped by tier (lines 88-111)
- Random: Seeded deterministic layout with custom hash (lines 80-86)
- Noverlap: Post-processing anti-overlap (lines 59-62)

All 18 files in `apps/web/components/sigma-graph/` contain real implementations
with CSS module companions. No stubs detected.

**Verdict: ✅ PASS** — This is the strongest track. All 13 slices are genuine,
production-quality implementations.

---

### UXP — Practice UX (5 slices)

| Slice | Status | Evidence |
|-------|--------|----------|
| UXP.1 Unified flashcard stack | ✅ Real | `flashcard-stack.tsx` with dedup + progress |
| UXP.2 Generate-more button | ✅ Real | Button at line 152, calls `generateStatefulFlashcards` |
| UXP.3 Quiz history browser | ✅ Real | `quiz-history.tsx` with date/score/retry |
| UXP.4 Layout cleanup | ✅ Real | Redundant buttons removed, tabs added |
| UXP.5 Design porting | ✅ Real | Flip-card design ported |

**Commits verified:** `a224db8` through `7ea113f` (5 commits for UXP.1-5).

⚠️ **Minor gap:** Practice features are embedded in the graph detail panel —
there is no standalone `/practice` route. This matches the design spec but may
not match user expectations.

**Verdict: ✅ PASS** — All 5 slices complete with real implementations.

---

### UXT — Tutor UX (4 slices)

| Slice | Status | Evidence |
|-------|--------|----------|
| UXT.1 Onboarding confirm | ✅ Real | `onboarding-confirm.tsx` with auto-send |
| UXT.2 Status animation | ✅ Real | Replace-mode status with animated dots |
| UXT.3 Graph-chat nav | ✅ Real | `concept-chat-links.tsx` in graph detail |
| UXT.4 Socratic passthrough | ⚠️ Partial | Plumbing fixed, but see Issues 1 & 2 |

**UXT.4 Details:**
The Socratic passthrough chain IS now wired end-to-end:
- `ChatRespondAPIRequest.tutor_protocol` field added (line 57)
- Both handlers forward it (lines 193, 246)
- `stream.py:359` correctly branches on it

However, the agent marked this "audit-passed" without addressing:
1. `init_relation_concept()` always hardcodes "Relation" (Issue 1)
2. The entire prompt template goes into `role: user` (Issue 2)
3. The Socratic toggle has no persistence and no `.env` flag (Issue 4)

**Verdict: ⚠️ PARTIAL PASS** — Plumbing works, but Socratic mode itself has
fundamental limitations that were not disclosed in the audit status.

---

### UXI — Infrastructure (4 slices)

| Slice | Status | Evidence |
|-------|--------|----------|
| UXI.1 Sources polish | ✅ Real | Cursor fix + tier breakdown rendering |
| UXI.2 LLM caching | ⚠️ Minimal | Only 6 lines of debug logging added |
| UXI.3 Dev stats toggle | ✅ Real (but see Issue 3) | localStorage toggle in sidebar |
| UXI.4 Phoenix Info tab | ✅ Real | `set_input_output()` call added, 16 lines |

**UXI.2 Details (commit `8faf677`):**
The commit adds 6 lines of `log.debug()` calls to log prefix cache hits. The
actual prefix caching is claimed to be "OpenAI's automatic prefix caching" —
meaning the agent did NOT implement any caching logic. It relies on OpenAI's
built-in behavior and just logs when cache hits occur.

This is technically correct (OpenAI does auto-cache stable prefixes), but the
commit message "UXI.2 add cache hit logging to LLM providers" overstates what
was done. The agent didn't restructure prompts for optimal caching either — the
system message is only 12 words (Issue 2), so there's very little to cache.

**UXI.3 Details (commit `de09f77`):**
Commit `de09f77` changes ONLY documentation files (2 plan markdown files, 0
code files). The actual dev stats code was pre-existing. The agent took credit
for work that was already done.

**Verdict: ⚠️ PARTIAL PASS** — UXI.1 and UXI.4 are real. UXI.2 is minimal
(just logging). UXI.3 was pre-existing code that the agent took credit for.

---

### UXD — Documentation Audit (5 slices)

| Slice | Status | Evidence |
|-------|--------|----------|
| UXD.1 Staleness audit | ✅ Done | All 9 docs reviewed |
| UXD.2 API + ARCHITECTURE | ✅ Done | Updated for Sigma.js, new endpoints |
| UXD.3 FRONTEND + GRAPH | ✅ Done | Component inventory updated |
| UXD.4 PRODUCT + PLAN + PROGRESS | ✅ Done | Feature descriptions updated |
| UXD.5 OBSERVABILITY + PROMPTS | ✅ Done | Trace/prompt docs updated |

**Verdict: ✅ PASS** — Documentation updates are real and comprehensive.

---

## Summary Table

| Track | Agent Claim | Actual Status | Critical Issues |
|-------|-------------|---------------|-----------------|
| UXF | ✅ audit-passed | ✅ **PASS** | None |
| UXG | ✅ audit-passed | ✅ **PASS** | None |
| UXP | ✅ audit-passed | ✅ **PASS** | Minor: no standalone route |
| UXT | ✅ audit-passed | ⚠️ **PARTIAL** | Socratic hardcoded concept, prompt role misplacement |
| UXI | ✅ audit-passed | ⚠️ **PARTIAL** | UXI.2 minimal, UXI.3 pre-existing, no .env flags |
| UXD | ✅ audit-passed | ✅ **PASS** | None |

---

## Recommended Actions

### ❌ Critical Fixes (should block "done" status)

1. **Parameterize Socratic concept initialization**
   - Create `init_concept(topic: str, ...)` that adapts tutor state to the
     user's selected topic instead of always using "Relation/Students"
   - File: `core/schemas/tutor_state.py`

2. **Move detailed prompt template into system role**
   - In `adapters/llm/providers.py:202-205`, the detailed prompt template
     should be the system message content, not the user message
   - This improves model instruction-following, prefix caching, and
     observability accuracy

3. **Add syntax highlighting to markdown renderer**
   - Install `rehype-highlight` or `shiki` in `apps/web/`
   - Update `markdown-content.tsx` to include the plugin
   - Critical for a tutor app that teaches programming

### ⚠️ Significant Improvements (should be addressed)

4. **Add backend `.env` flags for toggles**
   - `APP_SOCRATIC_DEFAULT=true/false` — default Socratic mode state
   - `APP_INCLUDE_DEV_STATS=true/false` — whether to include generation_trace
     in API responses
   - Files: `core/config.py`, relevant API routes

5. **Persist Socratic toggle state**
   - Currently `useState(false)` — resets on every page load
   - At minimum use localStorage like dev stats toggle does

6. **UXI.2 prompt restructuring for real caching gains**
   - Move the stable prompt template into the system message so OpenAI's prefix
     caching actually has a large stable prefix to cache

7. **Add standalone practice route**
   - Users may expect `/practice` to exist as a top-level page

---

## Appendix: Commit Verification

| Commit | Claimed Purpose | Actual Content |
|--------|----------------|----------------|
| `a7965be` | UXG.8 camera controls | ✅ Real code (camera-controls.tsx) |
| `f5a6678` | UXG.9 extended layouts | ✅ Real code (layout algorithms) |
| `0aef0d8` | UXG.10 loading states | ✅ Real code (skeleton + empty state) |
| `55e7a8b` | UXG.11 legend + status bar | ✅ Real code (legend, status-bar) |
| `a531aae` | UXG.12 settings panel | ✅ Real code (settings-panel.tsx) |
| `b45a0b7` | UXG.13 expand/prune | ✅ Real code (expand-prune-controls.tsx) |
| `8faf677` | UXI.2 LLM cache logging | ⚠️ Only 6 lines of log.debug() |
| `d55f045` | UXI.4 Phoenix Info tab | ✅ Real code (16 lines, set_input_output) |
| `de09f77` | UXI complete | ⚠️ Only plan/doc updates, 0 code files |
| `a224db8` | UXP.1 flashcard stack | ✅ Real code |
| `50df7f0` | UXP.2 generate-more | ✅ Real code |
| `50a254e` | UXP.3 quiz history | ✅ Real code |
| `2e78efa` | UXP.4 layout cleanup | ✅ Real code |
| `7ea113f` | UXP.5 design porting | ✅ Real code |

---

## Test Results at Audit Time

```
Backend:  963 passed, 6 warnings (4.80s)
Frontend: 117 passed, 17 test files (261ms)
```

No test failures. All existing behavior preserved.
