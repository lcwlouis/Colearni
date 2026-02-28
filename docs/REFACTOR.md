# CoLearni — Refactor Roadmap

> Generated as part of the G0–G4 non-functional audit.  
> No behavioral changes should be introduced by following this plan.

---

## 1. Oversized File Inventory (Top 15)

| # | File | Lines | Why it grew | Severity |
|---|------|------:|-------------|----------|
| 1 | `apps/web/app/globals.css` | 2424 | Single monolith CSS file for all pages, components, and utilities. Mixed concerns: sidebar, graph, chat, KB, theme, buttons, modals, animations. | 🔴 Critical |
| 2 | `domain/learning/level_up.py` | 1612 | Complex quiz/level-up domain logic — question generation, scoring, difficulty curves, spaced repetition scheduling. Multiple responsibilities in one module. | 🔴 Critical |
| 3 | `adapters/db/graph_repository.py` | 1099 | All graph persistence queries (CRUD, traversal, search, aggregation) in one file. Many similar but distinct query patterns. | 🟡 High |
| 4 | `domain/learning/practice.py` | 724 | Practice session orchestration, question selection, answer evaluation, progress tracking. | 🟡 High |
| 5 | `apps/web/app/tutor/page.tsx` | 686 | Entire tutor chat page in one component — state management, message rendering, concept switch UI, composer, progress bars, phase indicators. | 🟡 High |
| 6 | `domain/chat/respond.py` | 672 | Chat response pipeline — prompt assembly, context retrieval, LLM call, concept resolution, post-processing. Multiple pipeline stages in one file. | 🟡 High |
| 7 | `domain/graph/resolver.py` | 659 | Concept resolution with fuzzy matching, embedding similarity, alias handling, confidence scoring. | 🟡 Medium |
| 8 | `core/schemas.py` | 634 | All Pydantic schemas for the entire app — API request/response, domain DTOs, graph types, chat types, quiz types. | 🟡 Medium |
| 9 | `domain/graph/explore.py` | 555 | Graph exploration queries — neighbors, subgraph, filtering, search, highlight. | 🟢 Medium |
| 10 | `domain/graph/gardener.py` | 547 | Graph maintenance — merging, pruning, edge weight recalculation, consistency checks. | 🟢 Medium |
| 11 | `core/ingestion.py` | 487 | Upload + async ingestion pipeline — chunking, embedding, summarization, graph extraction. | 🟢 Medium |
| 12 | `apps/web/components/global-sidebar.tsx` | 478 | Sidebar navigation, session list, workspace management, profile, theme toggle, collapsed controls, context menus. | 🟢 Medium |
| 13 | `apps/web/lib/api/types.ts` | 443 | All TypeScript API types in one file. | 🟢 Low |
| 14 | `apps/web/app/kb/page.tsx` | 437 | Knowledge base page — upload, table, empty state, status badges, delete. | 🟢 Low |
| 15 | `core/observability.py` | 426 | OpenTelemetry setup, tracer provider, span utilities, Phoenix integration. | 🟢 Low |

---

## 2. Proposed Module / Component / CSS Splits

### 2.1 CSS Split Strategy (Critical — `globals.css` → domain files)

**Current state:** One 2424-line file mixing design tokens, component styles, page layouts, animations, and utilities.

**Proposed split (7 files):**

```
apps/web/app/
├── globals.css              # ~200 lines: CSS reset, variables, tokens, body, layout shell
├── styles/
│   ├── sidebar.css          # ~350 lines: .global-sidebar, .nav-link, .session-*, collapsed-*, profile
│   ├── chat.css             # ~400 lines: .chat-*, .message-*, .composer-*, phase indicators
│   ├── graph.css            # ~300 lines: .graph-*, .concept-graph-*, .graph-drawer, panels
│   ├── kb.css               # ~250 lines: .kb-*, table, upload queue, empty state
│   ├── components.css       # ~350 lines: buttons, .icon-btn, badges, modals, cards, .theme-toggle
│   └── utilities.css        # ~150 lines: animations, responsive utilities, accessibility
```

**Migration approach:**
1. Create the `styles/` directory and empty files.
2. Move rules top-down by section comments (already present in globals.css).
3. Import all partials in `layout.tsx` or a central `styles/index.css`.
4. Verify build + visual regression (screenshot comparison or manual).
5. One PR per file extraction to keep diffs small.

**Convention going forward:** New styles go in the domain-specific file. No new rules in `globals.css` except tokens.

### 2.2 Backend Module Splits

#### `domain/learning/level_up.py` (1612 lines → 4 files)
```
domain/learning/
├── level_up.py              # ~300 lines: orchestration, public API (generate_quiz, submit_answer)
├── question_gen.py          # ~400 lines: question generation strategies, LLM prompts
├── scoring.py               # ~300 lines: scoring logic, difficulty curves, mastery calculation
└── spaced_repetition.py     # exists (keep as-is)
```
- Public interface: `generate_quiz()`, `submit_answer()`, `get_progress()` stay in `level_up.py`.
- Internal helpers move to new modules, imported by `level_up.py`.

#### `adapters/db/graph_repository.py` (1099 lines → 3 files)
```
adapters/db/
├── graph_repository.py      # ~300 lines: CRUD (create/read/update/delete concept/edge)
├── graph_queries.py         # ~400 lines: traversal, neighbor search, subgraph extraction
└── graph_aggregation.py     # ~300 lines: statistics, counts, aggregation queries
```
- Repository class stays; complex queries extract into helper functions.

#### `core/schemas.py` (634 lines → domain-grouped files)
```
core/
├── schemas/
│   ├── __init__.py          # re-exports for backward compatibility
│   ├── chat.py              # chat request/response schemas
│   ├── graph.py             # graph/concept/edge schemas
│   ├── learning.py          # quiz, practice, progress schemas
│   ├── kb.py                # document, chunk, upload schemas
│   └── common.py            # shared base schemas, pagination, errors
```
- All existing imports like `from core.schemas import X` keep working via `__init__.py` re-exports.

#### `domain/chat/respond.py` (672 lines → 3 files)
```
domain/chat/
├── respond.py               # ~250 lines: main respond() function, orchestration
├── prompt_assembly.py       # ~200 lines: build_messages(), context formatting
└── post_processing.py       # ~150 lines: citation extraction, confidence scoring
```

### 2.3 Frontend Component Splits

#### `apps/web/app/tutor/page.tsx` (686 lines → 4 files)
```
apps/web/app/tutor/
├── page.tsx                  # ~200 lines: page shell, state init, layout
├── components/
│   ├── chat-messages.tsx     # ~200 lines: message list rendering, message bubbles
│   ├── chat-composer.tsx     # ~100 lines: input form, send button, phase indicator
│   └── concept-switch.tsx    # ~80 lines: concept switch suggestion banner
```

#### `apps/web/components/global-sidebar.tsx` (478 lines → 3 files)
```
apps/web/components/
├── global-sidebar.tsx        # ~200 lines: shell, nav, collapsed/expanded toggle
├── sidebar/
│   ├── session-list.tsx      # ~150 lines: recent chats list, rename/delete/context menu
│   └── workspace-picker.tsx  # ~120 lines: workspace select, create/rename forms, collapsed popover
```

---

## 3. Refactor Roadmap (Small PR Steps)

Each step is a standalone PR. No step changes behavior.

### Phase 1: CSS Extraction (4 PRs)
| PR | Description | Files | Safety Check |
|----|-------------|-------|------|
| 1a | Extract design tokens + reset into trimmed `globals.css` | `globals.css` → `globals.css` + `styles/` scaffold | Build + visual check |
| 1b | Extract sidebar CSS to `styles/sidebar.css` | Move `.global-sidebar`, `.nav-link`, `.session-*`, `.collapsed-*` | Build + sidebar visual check |
| 1c | Extract chat + graph CSS | Move `.chat-*`, `.graph-*` | Build + page checks |
| 1d | Extract KB + components + utilities CSS | Move `.kb-*`, buttons, modals, animations | Build + full app check |

### Phase 2: Backend Splits (3 PRs)
| PR | Description | Files | Safety Check |
|----|-------------|-------|------|
| 2a | Split `level_up.py` into question_gen, scoring | `domain/learning/` | `pytest tests/` (all pass) |
| 2b | Split `graph_repository.py` into queries + aggregation | `adapters/db/` | `pytest tests/db/` |
| 2c | Split `schemas.py` into domain packages | `core/schemas/` | `pytest tests/` + import checks |

### Phase 3: Frontend Splits (2 PRs)
| PR | Description | Files | Safety Check |
|----|-------------|-------|------|
| 3a | Extract tutor sub-components | `apps/web/app/tutor/` | Vitest + build + visual check |
| 3b | Extract sidebar sub-components | `apps/web/components/sidebar/` | Vitest + build + visual check |

### Phase 4: Cleanup (1 PR)
| PR | Description | Files | Safety Check |
|----|-------------|-------|------|
| 4a | Remove dead code, consolidate duplicate CSS rules, clean up inline styles | Various | Build + all tests |

---

## 4. Mobile Readiness Checklist

> Do NOT implement these changes now. This is a documentation-only audit.

### 4.1 Responsive Layout Breakpoints (currently missing)

- [ ] **Define breakpoints:** `sm: 640px`, `md: 768px`, `lg: 1024px`, `xl: 1280px`
- [ ] **Add viewport meta tag** (already present via Next.js defaults)
- [ ] **Audit all `@media` queries** — currently only `(max-width: 767px)` for graph panels and `(min-width: 768px)` for some overrides. No consistent system.

### 4.2 Sidebar Behavior

- [ ] **Mobile sidebar:** Convert to drawer/overlay (slide in from left, overlay backdrop)
- [ ] **Hamburger menu button** in mobile header to toggle sidebar
- [ ] **Auto-close sidebar** on navigation (mobile only)
- [ ] **Swipe gesture** to open/close sidebar (nice-to-have)
- [ ] **Backdrop click** closes sidebar on mobile

### 4.3 Graph Panel Layout

- [ ] **Single column on mobile:** Graph fills full width, details panel stacks below
- [ ] **Graph touch interactions:** Pinch-to-zoom, drag-to-pan (d3-zoom already supports touch)
- [ ] **Details panel:** Full-width drawer or bottom sheet on mobile
- [ ] **Search/filter controls:** Collapse into a sticky top bar
- [ ] **Node info tooltip:** Tap instead of hover; dismiss on outside tap

### 4.4 Chat Layout

- [ ] **Full-width messages** on mobile (no max-width constraint)
- [ ] **Sticky composer** at bottom of viewport
- [ ] **Concept switch banner:** Full-width, stacked buttons instead of inline
- [ ] **Phase indicator:** Compact; consider inline with composer
- [ ] **Virtual keyboard handling:** Auto-scroll to bottom when keyboard opens

### 4.5 Sources (KB) Page

- [ ] **Responsive table → card layout** on mobile (each document as a card)
- [ ] **Upload area:** Full-width drop zone; file input accessible
- [ ] **Action buttons:** Move to swipe actions or overflow menu on cards
- [ ] **Column hiding:** Hide less important columns (chunks, date) on narrow screens
- [ ] **Empty state:** Already responsive (flexbox), just verify on small screens

### 4.6 General

- [ ] **Touch targets:** Minimum 44×44px for all interactive elements
- [ ] **Font scaling:** Use `rem`/`em` units (mostly done)
- [ ] **Horizontal scroll prevention:** Ensure no element overflows viewport
- [ ] **Orientation support:** Landscape mode considerations for graph
- [ ] **Safe area insets:** Handle notch/dynamic island on iOS (`env(safe-area-inset-*)`)
- [ ] **Performance:** Lazy-load graph visualization on mobile; reduce initial bundle

### 4.7 Priority Order for Mobile Implementation
1. Sidebar → drawer overlay (highest impact)
2. Chat layout (core UX)
3. KB table → cards
4. Graph panel stacking (already partially done)
5. Touch optimizations (polish)

---

## 5. Quick Wins vs. Deeper Changes

### Quick Wins (can be done in 1-2 hours each)
- Split `globals.css` into domain files (mechanical move)
- Split `core/schemas.py` into subpackage (backward-compatible re-exports)
- Extract `concept-switch.tsx` from tutor page (self-contained JSX block)
- Remove inline styles from `global-sidebar.tsx` (move to CSS classes)

### Deeper Changes (half-day to full-day each)
- Split `level_up.py` (needs careful function boundary analysis)
- Split `graph_repository.py` (SQL queries need grouping review)
- Extract tutor sub-components (state passing needs design)
- Mobile sidebar drawer (new component + animation + gesture handling)

---

*Last updated: Post D4 completion, pre-mobile implementation.*
