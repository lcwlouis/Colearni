# AU Port Backlog: `copilotv0.2` → `copilotv2.0`

> **Context:** `copilotv0.2` and `copilotv2.0` diverged from commit `208c1dc`
> (`chore(refactor): OBS-7 completion audit and verification ledger`) on **2026-03-01 02:54 UTC**.
> A clean `git merge` is not possible — 71 conflict hunks across 25 production files.
> The recommended approach is to **port changes selectively** from `copilotv0.2` into `copilotv2.0`.
>
> Use the **Port?** column to mark each item: `[ ]` = skip, `[x]` = port it.

---

## How to Merge the Worktree Back

The `copilotv2.0` branch lives in its own git worktree at:
```
/Users/louisliu/Projects/Personal/copilotv2.0
```

### Option A — Cherry-pick individual commits (Recommended)

Work directly inside the `copilotv2.0` worktree:
```bash
cd /Users/louisliu/Projects/Personal/copilotv2.0

# List the AU commits you want to port (from copilotv0.2)
git --no-pager log --oneline copilotv0.2 --not copilotv2.0

# Cherry-pick a specific commit
git cherry-pick <commit-sha>

# If there are conflicts, resolve them, then:
git add .
git cherry-pick --continue
```

### Option B — Manual file-level port

For changes that conflict heavily, copy the specific functions/blocks by hand:
```bash
# See exactly what a commit changed
git --no-pager show <commit-sha> -- path/to/file.py

# Or diff a specific file between branches
git --no-pager diff copilotv2.0...copilotv0.2 -- domain/chat/turn_policy.py
```

### Option C — Force merge (nuclear, not recommended)

If you want to attempt a merge and resolve all 25 conflicting files manually:
```bash
cd /Users/louisliu/Projects/Personal/copilotv2.0
git merge copilotv0.2 --no-ff
# Resolve all conflicts, then:
git add .
git merge --continue
```

> ⚠️ Option C will conflict in: `core/schemas/`, `domain/chat/` (8 files),
> `domain/learning/`, `apps/api/routes/`, and 6 frontend files.

### After porting — remove the worktree

Once you're done porting and `copilotv2.0` is your canonical branch:
```bash
# From the main repo root
git worktree remove /Users/louisliu/Projects/Personal/copilotv2.0

# Or if there are uncommitted changes you want to discard:
git worktree remove --force /Users/louisliu/Projects/Personal/copilotv2.0

# Optionally delete the branch if it's fully merged
git branch -d copilotv0.2
```

---

## AU Port Backlog

### AU1 — Grounding / Turn Policy

| Commit(s) | Change | What it fixes | Severity | Port? |
|-----------|--------|---------------|----------|-------|
| AU1.1–AU1.4 | New `domain/chat/turn_policy.py` — `TurnPolicy` dataclass + `build_turn_policy()` | Prevents citation refusals on clarification/social turns; decouples intent classification from citation enforcement | 🔴 Core behaviour | [ ] |
| AU1.2 | Query analysis gates retrieval in `respond.py` + `stream.py` — skip `retrieve_ranked_chunks()` when `requires_retrieval=False` | Stops vector search firing on every turn regardless of intent; cuts latency on social/clarification turns | 🔴 Core behaviour | [ ] |
| AU1.3 | `strict_grounded: bool` param threaded through all `prompt_kit.py` + `tutor_agent.py` builders | Hybrid-mode was still instructing the LLM to behave as strict-grounded, causing over-refusals | 🟠 Correctness bug | [ ] |
| AU1.4 | `verify_assistant_draft()` gains `turn_policy` kwarg; short-circuits citation check when `requires_citations=False` | Hybrid clarification turns were failing with `kind=refusal, refusal_reason=invalid_citations` | 🔴 Core behaviour | [ ] |
| AU1.5 | `social_intent_enabled` default → `False` in `core/settings.py` | Prevents ungrounded social fast-path responses in production by default | 🟡 Safe default | [ ] |
| AU1.6 | `run_query_analysis()` convenience wrapper in `domain/chat/query_analyzer.py` | Removes duplicated try/except boilerplate at every call site | 🟢 DX / safety | [ ] |
| AU1.7 | `ConceptSwitchBanner` → inline non-blocking banner (was full modal); "Dismiss" no longer auto-fires a chat message | Old modal blocked entire chat UI; auto-fire triggered unintended LLM calls on dismiss | 🟠 UX bug fix | [ ] |
| AU1.8 | Confidence-gap guard `_SWITCH_CONFIDENCE_GAP = 2.0` in `concept_resolver.py` | Any scoring margin (even 0.1) triggered noisy concept-switch suggestions | 🟠 UX bug fix | [ ] |
| AU1.9 | Persona social-reply strings moved to `PERSONA_COLEARNI` dict keys (`thanks_reply`, `farewell_reply`, etc.) | Hard-coded strings couldn't be customised per deployment | 🟢 DX | [ ] |

### AU2 — Quiz / Learning Memory

| Commit(s) | Change | What it fixes | Severity | Port? |
|-----------|--------|---------------|----------|-------|
| AU2.1 | Flashcard run retrieval: `list_flashcard_runs()`, `get_flashcard_run_cards()`, new API routes + Pydantic schemas + frontend `ApiClient` methods + "Prior runs" UI | Users couldn't revisit previously generated flashcard decks | 🟠 Missing feature | [ ] |
| AU2.2 | Quiz retrieval: `list_quizzes()`, `get_quiz_detail()`, `list_quiz_attempt_summaries()`, new API routes + schemas + frontend types + "View prior quizzes" UI | Quiz history was write-only; prior attempts invisible to users and LLM | 🟠 Missing feature | [ ] |
| AU2.3 | `load_existing_graded_attempt` → `ORDER BY id DESC` (latest, not first) | Re-submission returned the oldest/stale grade instead of the most recent | 🟠 Data bug fix | [ ] |
| AU2.4 | `retry: bool = False` flag on `submit_quiz()` + `submit_practice_quiz()`; mastery floor guard on retries | Retrying a quiz returned cached stale result; mastery could regress on retry | 🟠 Missing feature | [ ] |
| AU2.5 | `_build_learning_summary()` injected into practice/flashcard generation context (last 10 flashcard ratings + last 3 quiz scores) | LLM generating new questions had no knowledge of prior performance | 🟠 Adaptive learning | [ ] |
| AU2.6 | `_OVERFETCH_MAX = 10` caps unbounded overfetch ceiling in `practice.py` | Unbounded overfetch could request 50+ items from LLM, blowing token budgets | 🔴 Budget / safety | [ ] |
| AU2.7 | Prior quiz attempts (limit 5) appended to `build_quiz_context()` in `response_service.py` | Tutor had no memory of past quiz scores for the same concept | 🟠 LLM context quality | [ ] |
| AU2.8 | Magic numbers → named constants in `quiz_flow.py` (`ADJACENT_CONCEPTS_LIMIT`, `MAX_CHAT_HISTORY_TURNS`) | Minor code quality; constants now configurable without touching logic | 🟢 Code quality | [ ] |

### AU3 — Graph Extraction / Onboarding

| Commit(s) | Change | What it fixes | Severity | Port? |
|-----------|--------|---------------|----------|-------|
| AU3.1 | LLM reranking of onboarding start suggestions (`_llm_rerank()`) + 5-min TTL cache in `domain/onboarding/status.py` | Degree-centrality ranking surfaced advanced/abstract concepts as entry points instead of foundational ones | 🟠 UX quality | [ ] |
| AU3.2 | `invalidate_suggestion_cache(workspace_id)` called from `run_post_ingest_tasks()` | Stale onboarding suggestions served for up to 5 min after new documents were uploaded | 🟠 Correctness | [ ] |
| AU3.3 | Concept name length guard `_MAX_CONCEPT_NAME_CHARS = 80` in `domain/graph/extraction.py` | Sentence-fragment concept names polluted the graph with non-canonical, never-merging nodes | 🟠 Data quality | [ ] |
| AU3.4 | Extraction prompt (`extract_chunk_v1.md`) gains 4 new quality rules: name ≤5 words, avoid generic terms, edges only for meaningful relationships, prefer durable concepts | Low-quality/generic concepts and spurious co-occurrence edges degraded graph + resolver quality | 🟠 Data quality | [ ] |
| AU3.5 | Substring-containment merge step `_deterministic_substring_decision()` in `domain/graph/resolver.py` (fires before lexical check, confidence 0.90) | Obvious containment pairs ("Back-propagation" / "Backpropagation Algorithm") slipped past embedding similarity | 🟠 Graph quality | [ ] |
| AU3.6 | Remove `domain/ingestion/document_status.py` placeholder stub | Placeholder-only file was importable but did nothing | 🟢 Cleanup | [ ] |

### AU4 — Runtime Observability / Logging

| Commit(s) | Change | What it fixes | Severity | Port? |
|-----------|--------|---------------|----------|-------|
| AU4.1 | Startup `WARNING` logs in `apps/api/main.py` when `embedding_provider == "mock"` or `graph_llm_provider == "mock"` | Mock providers silently returned stub responses in staging/production when env vars were missing | 🟡 Operability | [ ] |
| AU4.2 | `log.warning(...)` in LLM failure catch blocks in `practice.py` and `quiz_flow.py` before falling back | LLM generation failures were silently swallowed; fallback content served with no trace | 🟡 Observability | [ ] |
| AU4.3 | `log.warning(...)` in tutor agent `except` block in `domain/chat/tutor_agent.py` | Same silent-fallback gap in the tutor LLM path | 🟡 Observability | [ ] |
| AU4.4 | Stream path emits span attributes: `chat.grounding_mode`, `chat.verifier_result`, `chat.response_mode`, `chat.refusal_reason`, + all turn-policy booleans | Streaming traces were missing all grounding/audit fields | 🟠 Audit completeness | [ ] |

### AU0 — Infrastructure / Packaging

| Commit(s) | Change | What it fixes | Severity | Port? |
|-----------|--------|---------------|----------|-------|
| AU0.1 | `pyproject.toml` at repo root with pinned runtime deps, dev extras, pytest config, ruff config | No canonical packaging manifest; `pip install -e .` didn't work cleanly | 🟠 Infra | [ ] |
| AU0.2 | `.nvmrc` pins Node.js version for frontend | Different Node versions caused `npm install` and build divergences across machines | 🟢 Infra | [ ] |

---

## Port Priority Guide

| Severity | Meaning |
|----------|---------|
| 🔴 Core behaviour | Correctness or budget issue — should port before shipping |
| 🟠 Correctness / Missing feature | Real user-facing bug or gap — high value to port |
| 🟡 Observability / Safe default | Operational hygiene — port when convenient |
| 🟢 DX / Cleanup | Code quality — low urgency |

---

## Suggested Port Order

If you're running the AU audit on `copilotv2.0`, suggested sequence:

1. **AU0.1** — `pyproject.toml` first (makes the dev environment consistent)
2. **AU1.1–AU1.4** together — `TurnPolicy` module + wiring into respond/stream/verifier (these are tightly coupled)
3. **AU2.6** — `_OVERFETCH_MAX` (single-line, high safety value)
4. **AU2.3** — quiz grade ordering fix (trivial SQL change, high correctness value)
5. **AU3.3 + AU3.4** — extraction quality guards (independent of schema changes)
6. **AU3.5** — substring merge in resolver (independent module)
7. **AU2.1 + AU2.2** — flashcard/quiz retrieval APIs (larger, but self-contained)
8. **AU1.7 + AU1.8** — banner UX + concept-switch confidence gap (frontend + backend)
9. **AU2.4 + AU2.5 + AU2.7** — quiz retry, learning context, quiz history in chat
10. **AU3.1 + AU3.2** — LLM onboarding reranking + cache invalidation
11. **AU4.x** — observability pass (safe to batch)
