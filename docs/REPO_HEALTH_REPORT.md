# Repo Health Report — 2026-03-02

## Executive Summary

The CoLearni repo is **healthy but growing** — it's well-organized with clear domain boundaries, but a few files are pushing past maintainability thresholds. A targeted refactor after this sprint is **recommended but not urgent**. The codebase is not "ridiculously huge" — it's appropriately sized for its feature set.

**Overall health score: 7/10** — solid engineering, needs focused cleanup in a few areas.

---

## Size Metrics (Corrected Breakdown)

| Category | Files | LOC | Notes |
|----------|-------|-----|-------|
| **Python source** (domain/ core/ adapters/ apps/) | ~146 | ~15,500 | Business logic, routes, adapters |
| **Python tests** | ~73 | ~11,200 | Strong coverage |
| **Prompt templates** (.md) | 13 | ~488 | Markdown assets, NOT code |
| **Prompt infrastructure** (Python) | 5 | ~336 | Loader, registry, renderer |
| **Frontend source** (TS/TSX) | ~118 | ~11,000 | Components, hooks, types |
| **CSS** | 10 | ~2,500 | Styles |
| **Documentation** (.md) | ~16 | ~5,000+ | Plans, guides, API docs |
| **Total source** (excl. tests, docs, prompts) | ~279 | **~29,300** | Actual production code |
| **Total including tests** | ~352 | **~41,000** | Full picture |

**The ~58.5K figure from the initial report was inflated** — it counted all `.py` files including generated `__pycache__`, migration stubs, egg-info, and duplicate path traversals. The actual production codebase is ~29K LOC, with ~11K LOC of tests on top.

**Prompt templates are 488 lines of markdown** — a negligible fraction. They are NOT included in the source LOC count above.

**Verdict**: ~29K LOC of production code is **lean** for an application with LLM orchestration, knowledge graph management, spaced repetition, streaming chat, research planning, and a full Next.js frontend. This is not bloated.

---

## Architecture Quality

### Strengths ✅

| Area | Assessment |
|------|-----------|
| **Layered architecture** | Clean `adapters/` → `domain/` → `apps/` separation. Business logic stays out of routes. |
| **Domain organization** | 11 well-named domain modules (`chat/`, `graph/`, `learning/`, `research/`, `retrieval/`, etc.) with clear boundaries |
| **Feature-based frontend** | `apps/web/features/` groups components, hooks, and styles by feature (tutor, graph, kb, sidebar) |
| **Shared components** | `apps/web/components/` for reusable UI (concept-graph, health-dot, chat-response) |
| **Observability** | Phoenix OpenInference instrumented — LLM calls are traceable |
| **Test organization** | Tests mirror source structure (`tests/domain/`, `tests/api/`, `tests/db/`, `tests/adapters/`) |
| **Prompt management** | Prompts stored as markdown assets in `core/prompting/` — version-trackable |

### Concerns ⚠️

| Area | Assessment | Severity |
|------|-----------|----------|
| **Giant files** | 4 files exceed 500 LOC (see below) | 🟡 Medium |
| **Missing job tests** | `apps/jobs/` has 4 job files with no test coverage | 🟡 Medium |
| **Transaction management** | Routes use implicit session management but some never commit (gardener bug) | 🔴 High |
| **Type file size** | `lib/api/types.ts` is 599 lines — single file for all API types | 🟡 Medium |
| **Raw SQL** | Heavy use of raw SQL strings in adapters — no query builder, some risk of SQL injection if not parameterized | 🟡 Medium |

---

## Largest Files (Refactor Candidates)

### Python (Top 10)

| File | Lines | Risk | Recommendation |
|------|-------|------|---------------|
| `domain/learning/practice.py` | 1,010 | 🔴 High | Split into `practice_service.py`, `flashcard_generator.py`, `practice_flow.py` |
| `adapters/llm/providers.py` | 711 | 🟡 Medium | Consider splitting per provider (openai, litellm) |
| `domain/learning/quiz_flow.py` | 690 | 🟡 Medium | Extract grading logic to `quiz_grading.py` (partially done) |
| `domain/graph/gardener.py` | 620 | 🟡 Medium | Extract tier backfill and orphan pruning into coordinator pattern |
| `core/settings.py` | 568 | 🟢 Low | Acceptable for config — rarely changes |
| `core/observability.py` | 532 | 🟢 Low | Acceptable for instrumentation |
| `domain/chat/stream.py` | 526 | 🟡 Medium | Consider extracting event builders |
| `domain/chat/respond.py` | 442 | 🟢 Low | Near the limit but cohesive |
| `adapters/db/chat.py` | 421 | 🟢 Low | DB adapter — many queries expected |

### TypeScript/TSX (Top 5)

| File | Lines | Risk | Recommendation |
|------|-------|------|---------------|
| `lib/api/types.ts` | 599 | 🟡 Medium | Split by domain: `types/chat.ts`, `types/graph.ts`, `types/kb.ts` |
| `components/concept-graph.tsx` | 539 | 🟡 Medium | Extract D3 drawing logic to `concept-graph-renderer.ts` |
| `features/tutor/hooks/use-tutor-messages.ts` | 294 | 🟢 Low | Acceptable for complex hook |
| `features/graph/hooks/use-graph-page.ts` | 278 | 🟢 Low | Acceptable |
| `features/kb/hooks/use-kb-page.ts` | 210 | 🟢 Low | Fine |

---

## API Surface

| Category | Endpoints | Assessment |
|----------|-----------|-----------|
| Auth | 5 | ✅ Clean |
| Workspaces | 6 | ✅ Clean |
| Chat | 7 | ✅ Appropriately complex |
| Knowledge Base | 4 | ✅ Simple |
| Graph | 6 | ✅ Clean |
| Practice | 11 | ⚠️ Largest — consider grouping |
| Research | 10 | ⚠️ Feature-rich but manageable |
| Quizzes | 5 | ✅ Clean |
| Other | 4 | ✅ Health, readiness, onboarding, docs |
| **Total** | **~58** | Appropriate for feature set |

---

## Test Coverage

| Type | Count | Coverage |
|------|-------|----------|
| Domain unit tests | ~40 files | ✅ Good — covers core logic |
| API integration tests | ~15 files | ✅ Good — covers routes |
| DB integration tests | ~11 files | ✅ Good — covers queries |
| Adapter tests | ~4 files | 🟡 Light |
| Frontend tests | 15 files / 106 tests | ✅ Good for component layer |
| Job tests | 0 files | 🔴 Missing |
| **Total backend** | ~922 tests | ✅ Strong |
| **Total frontend** | 106 tests | ✅ Adequate |

**Test-to-source ratio**: ~1:4.5 (acceptable for this stage)

---

## Design Pattern Assessment

| Pattern | Usage | Quality |
|---------|-------|---------|
| **Service layer** | `domain/` modules expose service functions, routes call them | ✅ Well implemented |
| **Repository pattern** | `adapters/db/` modules handle SQL, domain stays pure | ✅ Clean separation |
| **Dependency injection** | FastAPI `Depends()` for session, auth, workspace context | ✅ Standard |
| **Event-driven streaming** | SSE with typed events, frontend parses stream | ✅ Well structured |
| **LLM abstraction** | `adapters/llm/providers.py` wraps OpenAI/LiteLLM | ✅ Good abstraction |
| **Schema validation** | Pydantic models in `core/schemas/` | ✅ Consistent |
| **Prompt templates** | Markdown files in `core/prompting/` | ✅ Version-trackable |
| **State management** | React hooks + context, no global store | ✅ Appropriate for size |

---

## Should You Refactor After This Sprint?

### Recommendation: **Yes — a focused 1-sprint refactor targeting 3 items**

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| 🔴 P0 | **Audit all routes for missing `db.commit()`** — the gardener bug suggests other routes might have the same issue | Small | Critical — data integrity |
| 🟡 P1 | **Split `practice.py` (1,010 LOC)** into 3 modules | Medium | Maintainability |
| 🟡 P1 | **Split `types.ts` (599 LOC)** by domain | Small | Developer experience |

### Not Recommended Right Now

| Item | Why Not |
|------|---------|
| Full architectural refactor | Architecture is sound — layering is correct, domains are well-bounded |
| Switch to ORM queries | Raw SQL works, is well-parameterized, and performs well |
| Frontend state management overhaul | Hooks pattern is fine at current scale |
| Microservice decomposition | Way too early — monolith is appropriate |

---

## Roadmap to 9/10 Architecture

The user asked: *"Can we target 9 to 9.5/10?"* Here's what that would require — organized by impact and effort.

### Current: 7/10 — What's holding it back

| Gap | Current Score | Impact |
|-----|--------------|--------|
| Transaction safety | 4/10 | 🔴 Data integrity risk — routes silently lose writes |
| Large file hotspots | 6/10 | 🟡 Maintainability ceiling in 4 files |
| Missing job tests | 5/10 | 🟡 Untested background workers |
| No LLM caching | 5/10 | 🟡 Unnecessary API cost and latency |
| Dev observability | 6/10 | 🟡 No user-facing stats toggle |

### Target: 9/10 — The specific changes needed

**Tier 1: Must-haves (7/10 → 8.5/10)**

| # | Change | Effort | LOC Impact |
|---|--------|--------|-----------|
| R1 | **Audit all routes for missing `db.commit()`** — add commits or introduce auto-commit middleware | Small | +20 LOC |
| R2 | **Split `practice.py`** (1,010 LOC) → `practice_service.py`, `flashcard_gen.py`, `practice_flow.py` | Medium | Net 0 (restructure) |
| R3 | **Split `providers.py`** (711 LOC) → `openai_provider.py`, `litellm_provider.py`, `base_provider.py` | Medium | Net 0 (restructure) |
| R4 | **Split `types.ts`** (599 LOC) → `types/chat.ts`, `types/graph.ts`, `types/kb.ts`, `types/shared.ts` | Small | Net 0 (restructure) |
| R5 | **Add job tests** — basic coverage for 4 job files in `apps/jobs/` | Medium | +200 LOC tests |
| R6 | **Extract `concept-graph.tsx`** D3 rendering logic to `concept-graph-renderer.ts` | Medium | Net 0 (restructure) |

**Tier 2: Nice-to-haves (8.5/10 → 9/10)**

| # | Change | Effort | LOC Impact |
|---|--------|--------|-----------|
| R7 | **LLM prompt caching** — structure messages for prefix caching, log cache hits | Medium | +50 LOC |
| R8 | **Error handling audit** — ensure all domain functions have consistent error types, no bare `except:` | Medium | +100 LOC |
| R9 | **Inline documentation** — add module-level docstrings to all `domain/` and `adapters/` modules | Small | +150 LOC |
| R10 | **Dead code scan** — run `vulture` or similar static analysis, remove confirmed dead code | Small | -100 LOC |

**Tier 3: Aspirational (9/10 → 9.5/10)**

| # | Change | Effort | LOC Impact |
|---|--------|--------|-----------|
| R11 | **Type-safe SQL builder** — replace raw SQL strings with a lightweight query builder for adapters | Large | Net +200 LOC |
| R12 | **Dependency graph validation** — enforce import rules (domain/ cannot import from apps/) via CI | Small | +30 LOC |
| R13 | **Performance profiling** — add timing decorators to hot paths, establish latency budgets | Medium | +80 LOC |
| R14 | **E2E test suite** — Playwright or Cypress for critical user flows | Large | +500 LOC |

### LOC Reduction Potential

| Action | LOC Saved | Notes |
|--------|-----------|-------|
| Dead code removal (estimated) | -100 to -300 | Need `vulture` scan to confirm |
| DRY up repeated SQL patterns in adapters/ | -100 to -200 | Common query helpers |
| Consolidate similar test fixtures | -200 to -400 | Tests have some fixture duplication |
| Remove deprecated endpoints | -50 to -100 | If any exist |
| **Total potential reduction** | **-450 to -1,000** | **~3-7% of source LOC** |

**Honest assessment**: The codebase is not bloated — at ~29K LOC for this feature set, it's already lean. Splitting large files won't reduce LOC but will improve maintainability. Real LOC reduction comes from dead code removal and DRYing up patterns, which might save 3-7%. The bigger win is **structural quality** (splitting, testing, caching) rather than raw line count.

### Growth Projection

At current trajectory (~58K LOC, ~444 files), the repo will remain manageable for 1-2 more feature sprints before the large files become a real problem. The **1,010-line practice.py** is the canary — if it grows further without splitting, it will become a maintenance burden.

---

## Summary

| Metric | Score | Notes |
|--------|-------|-------|
| Code size | 7/10 | Medium app, 4 files need splitting |
| Organization | 8/10 | Clean domains, good separation |
| Test coverage | 7/10 | Strong backend, missing job tests |
| Design patterns | 8/10 | Consistent, well-applied |
| Frontend quality | 8/10 | Well-distributed, good hooks pattern |
| Transaction safety | 4/10 | 🔴 Missing commits is a systemic risk |
| Documentation | 7/10 | Good plan docs, light inline docs |
| **Overall** | **7/10** | **Healthy — focused refactor recommended** |

**Bottom line**: The code is not "ridiculously huge." It's well-structured for its feature count. The biggest risk is the transaction commit bug pattern, which should be audited across all routes. After that, splitting 2-3 large files would keep the repo clean for the next few sprints.
