# Drift Report

As of 2026-02-28.

This report compares three baselines:

1. The original project description in the thread request.
2. The planning discussion in `tmp/pdfs/branch_colearni_discussion.txt`.
3. The current implementation in the repo.

## Executive Summary

The project has not drifted evenly.

- Compared with the later planning discussion, the app is mostly on-track.
- Compared with the original broad "learning copilot + second brain + research/search" vision, the app has drifted substantially toward a narrower product: a grounded learning workspace over user-uploaded materials.

The clearest pattern is this:

- The pedagogy layer is real.
- The graph layer is real.
- The upload-ground-retrieve-answer loop is real.
- The proactive research/search/knowledge-discovery layer is still mostly missing or only partially scaffolded.

So the product today is much closer to:

> "Graph-backed Socratic tutor with mastery-gated quizzes and practice"

than to:

> "Agentic second brain that finds, filters, researches, ingests, and periodically updates knowledge for the user"

## Bottom-Line Assessment

Estimated alignment, by baseline:

| Baseline | Estimated alignment | Summary |
| --- | --- | --- |
| Original broad vision | 35-45% | The learning/quiz/graph core exists, but the search, topic-finding, user-model, and deep-search second-brain layers are mostly absent. |
| Planning discussion | 70-80% | The implemented app matches the narrowed MVP surprisingly well: upload, graph, grounded tutor, quizzes, practice, mastery, graph explorer, jobs. |
| Current `docs/ARCHITECTURE.md` + `docs/PRODUCT_SPEC.md` | 75-85% | The docs mostly describe the current shape, but they overstate explicit "agent" boundaries and understate some implementation realities. |

These are directional estimates, not test-derived metrics.

## Current State Snapshot

The current app already has a meaningful vertical slice:

- Auth + multi-workspace support.
- Knowledge-base upload and reprocessing.
- Ingestion for `.txt`, `.md`, and `.pdf`.
- Chunking, embeddings, and hybrid retrieval.
- Raw + canonical concept graph with resolver and offline gardener.
- Chat tutor with evidence/citations and strict vs hybrid grounding.
- Mastery-gated behavior in tutor responses.
- Level-up quiz generation, submission, grading, and mastery update.
- Practice quizzes and flashcards from graph concepts.
- Graph explorer and "I’m feeling lucky" graph traversal.
- Readiness analyzer and quiz CTA actions.
- A working Next.js web app for KB, tutor, graph, and login.
- File-based prompt asset system (`core/prompting/`) with versioned assets per task family.
- Query analysis scaffold (`domain/chat/query_analyzer.py`) — exists and tested but not yet wired into the tutor runtime.

This is already a real product slice, not just scaffolding.

## Where The App Matches The Plan Well

### 1. Learning-first, anti-brainrot tutor

This is one of the strongest areas of alignment.

- The planning discussion narrowed the product around Socratic tutoring, mastery gating, and grounded responses.
- The current app implements that shape directly in chat response orchestration and tutor prompt building.

Current implementation:

- Chat response flow: `apps/api/routes/chat.py`, `domain/chat/respond.py`, `domain/chat/response_service.py`
- Evidence/citation verification: `core/verifier.py`
- Tutor style gating: `domain/chat/tutor_agent.py`

Assessment:

- Very close to the planning discussion.
- Moderately aligned with the original vision.

### 2. Graph-backed learning model

This is also close to plan.

- The planning discussion heavily emphasized LightRAG-inspired graph extraction, canonicalization, and bounded consolidation.
- The current app implements the raw/canonical graph split, online resolver budgets, and offline gardener.

Current implementation:

- Graph extraction pipeline: `domain/graph/pipeline.py`, `domain/graph/extraction.py`
- Online resolver: `domain/graph/resolver.py`
- Offline gardener: `domain/graph/gardener.py`
- Graph exploration API: `apps/api/routes/graph.py`, `domain/graph/explore.py`

Assessment:

- Very close to the planning discussion.
- More concrete and productized than the original description.

### 3. Quiz, mastery, and practice loops

This area is strong and materially complete.

- The planning discussion framed level-up quizzes as the progression mechanic and graph practice as non-leveling.
- The current app supports both.

Current implementation:

- Level-up quiz flow: `apps/api/routes/quizzes.py`, `domain/learning/level_up.py`
- Practice flow: `apps/api/routes/practice.py`, `domain/learning/practice.py`
- Readiness/review loop: `domain/readiness/analyzer.py`, `apps/jobs/readiness_analyzer.py`

Assessment:

- Very close to the planning discussion.
- More specific and disciplined than the original description.

### 4. Thin-route, Postgres-first implementation style

The repo follows the later planning discussion closely here.

- Routes are thin.
- Domain logic is mostly outside routes.
- Postgres is the single source of truth for chunks, graph, quizzes, mastery, and workspace state.

Current implementation:

- Thin routes throughout `apps/api/routes/*`
- Single-DB posture visible across `adapters/db/*`

Assessment:

- Strong alignment with the planning discussion.

## Where The Project Has Drifted Most From The Original Vision

### 1. Search-first topic discovery is mostly missing

This is the biggest gap versus the original plan.

The original description emphasized:

- topic finder agent
- knowledge finder agent
- search queries over web/papers/SME posts
- human-in-the-loop selection of POIs
- periodic topic expansion

Current state:

- There is no implemented search-planning agent.
- There is no topic-finder workflow that proposes subtopics from a prompt.
- There is no paper/post search orchestration layer.
- There is no user-visible POI selection loop.

What exists instead:

- A lightweight research subsystem for manually registered source URLs and background fetching.

Current implementation:

- Research routes: `apps/api/routes/research.py`
- Research CRUD service: `domain/research/service.py`
- Research runner: `domain/research/runner.py`, `apps/jobs/research_runner.py`

Assessment:

- High drift from the original description.
- Moderate underdelivery relative to the original "agentic research" ambition.
- Less drift relative to the later planning discussion, because that discussion intentionally narrowed the MVP around uploaded materials first.

### 2. The "current knowledge/config of user" is not implemented as a living user model

The original plan wanted a dynamic user knowledge/config file containing:

- summary of the knowledge base
- user preferences
- known knowledge
- weaker topics
- interests
- goals
- dates and summaries of ingested data

Current state is fragmented instead of unified:

- Workspace settings exist as generic JSON.
- A `user_tutor_profile` exists, but it currently exposes only `readiness_summary`, `learning_style_notes`, and `last_activity_at`.
- Mastery exists per concept.
- Readiness exists per topic.
- Chat memory exists.

What is missing:

- No single canonical learner profile object.
- No automatic updater that consolidates user preferences/interests/goals.
- No dynamic prompt profile comparable to the original concept.

Current implementation:

- Workspace settings: `apps/api/routes/workspaces.py`
- Tutor profile: `apps/api/routes/auth.py`, `adapters/db/auth.py`
- Mastery/readiness: `domain/learning/level_up.py`, `domain/readiness/analyzer.py`

Assessment:

- High drift from the original vision.
- The app has the data fragments, but not the original "living learner model" product behavior.

### 3. Deep-search / second-brain synthesis is not present

The original description explicitly wanted:

- a deep-search agent
- periodic synthesis of everything learned
- a current-knowledge review layer
- periodic updates about new developments

Current state:

- No deep-search synthesis agent exists.
- No periodic "everything learned" summary exists.
- No periodic external update pipeline exists.
- No user-facing second-brain review surface exists beyond graph browsing, chat history, and readiness.

Assessment:

- High drift from the original description.

## Where The Docs And The App Have Drifted From Each Other

The docs are fairly close to the current product shape, but there are important mismatches.

### 1. The docs describe more explicit agents than the code actually has

`docs/ARCHITECTURE.md` presents a clean "Conductor / Router" with `TutorAgent`, `LevelUpQuizAgent`, `PracticeAgent`, and `SuggestionAgent`.

Current implementation is less agentic and more function-oriented:

- chat orchestration is mostly `domain/chat/respond.py`
- quiz logic is mostly `domain/learning/level_up.py`
- practice logic is mostly `domain/learning/practice.py`
- "lucky" is implemented as graph exploration logic, not a dedicated suggestion agent

There is no general conductor module in `core/loop.py`, and the agent boundaries are mostly conceptual rather than hard runtime modules.

Assessment:

- Moderate docs-to-code drift.
- The product behavior exists, but the implementation is less explicitly "agentic" than the docs suggest.

### 2. "I'm feeling lucky" is simpler than the docs imply

The docs frame this like a dedicated suggestion capability.

Current implementation:

- `pick_lucky` is a bounded graph-selection function using graph topology and random choice.
- It does not currently generate a tutor hook or learning path via a dedicated LLM suggestion flow.

Current implementation:

- `apps/api/routes/graph.py`
- `domain/graph/explore.py`

Assessment:

- Moderate drift.
- The feature exists, but in a simpler deterministic form.

### 3. The docs say "UI later", but the web app already exists

`docs/ARCHITECTURE.md` still frames Next.js UI as "later".

Current implementation:

- Tutor UI: `apps/web/app/tutor/page.tsx`
- Graph UI: `apps/web/app/graph/page.tsx`
- Knowledge base UI: `apps/web/app/kb/page.tsx`
- Login and shell: `apps/web/app/login/page.tsx`, `apps/web/app/page.tsx`

Assessment:

- Low-to-moderate doc staleness.
- The app is ahead of that part of the architecture doc.

### 4. File-type support is ahead of the early narrow plan

The planning discussion initially recommended `.md` and `.txt` first, with PDF later.

Current implementation already supports PDF parsing:

- `adapters/parsers/text.py`
- Knowledge-base upload accepts `.txt`, `.md`, `.pdf` in `apps/web/app/kb/page.tsx`

Assessment:

- Positive drift.
- The app is ahead of the original MVP cut here.

### 5. The "in-chat card" model is only partially realized

The product docs describe level-up quizzes as in-chat cards.

Current state:

- The backend has quiz creation/submission flows.
- The frontend has a quiz drawer and result cards.
- Chat responses contain CTA actions.
- But quiz creation is still a separate route flow and UI drawer interaction, not a fully unified chat-native card runtime.

Assessment:

- Moderate implementation gap relative to the product wording.

## Drift Matrix By Feature Area

| Area | Original vision | Planning discussion | Current app | Drift verdict |
| --- | --- | --- | --- | --- |
| Grounded tutor | Important | Core MVP | Implemented | Low drift |
| Socratic gating | Important | Core MVP | Implemented | Low drift |
| Level-up quiz progression | Important | Core MVP | Implemented | Low drift |
| Practice from graph nodes | Mentioned later | Core MVP | Implemented | Low drift |
| Raw + canonical graph | Not explicit originally | Core MVP | Implemented | Low drift |
| Multi-workspace Postgres app | Not central originally | Strongly emphasized | Implemented | Low drift |
| Topic finder agent | Core original idea | Deprioritized for MVP | Missing | High drift vs original |
| Knowledge finder/search agent | Core original idea | Deprioritized for MVP | Mostly missing | High drift vs original |
| User config / learner model object | Core original idea | Only partially present later | Fragmented/partial | High drift |
| Periodic deep-search synthesis | Core original idea | Still conceptually desired | Missing | High drift |
| External source discovery | Core original idea | Deprioritized | Partial research scaffolding only | High drift |
| PDF support | Desired | Deferred | Implemented | Positive drift |
| Explicit agent runtime | Implied | Conceptually emphasized | Mostly functional modules | Moderate drift |
| Web UI | Optional/secondary | Optional then later | Implemented | Positive drift |

## Most Important Product Reframe

The project has effectively undergone a product reframe:

- Original: "agentic learning copilot and second brain that actively finds and curates new knowledge"
- Current: "grounded learning environment over user-uploaded material, with graph-backed tutoring and mastery workflows"

This is not necessarily bad drift.

In fact, it is probably the right MVP cut.

But it is important to name it clearly, because the current app does not yet support some of the most ambitious original use cases:

- learning a brand-new field through automatic discovery
- web-scale paper/post collection
- ongoing agentic updates about new developments
- a unified learner model that evolves automatically
- deep-search synthesis across everything the user has learned

## Recommendation

The right way to think about the current state is:

1. The pedagogical core is real and viable.
2. The graph architecture is real and viable.
3. The current app is a strong "Phase 1 learning workspace".
4. The original "second brain + research copilot" vision is mostly a Phase 2/3 layer that still needs deliberate design, not just incremental polish.

If you keep the current direction, the next major strategic choice is not "fix drift" in general.

It is:

- either fully commit to the narrower learning-workspace product, or
- deliberately reopen the original research-agent track and add it as a second product loop

without destabilizing the current tutor/graph/quiz foundation.

## Suggested Next-Step Themes

If the goal is to reduce drift from the original vision, the highest-leverage additions would be:

1. A real learner profile model.
   Consolidate workspace settings, tutor profile, mastery, readiness, interests, and recent ingestion into one coherent domain object.

2. A topic/search planning workflow.
   Add the missing topic finder and knowledge finder loop, with explicit human approval before ingestion.

3. A second-brain synthesis surface.
   Build periodic summaries of what the learner has covered, what is weak, and what has changed recently.

4. A true research ingestion loop.
   Evolve the current `research` subsystem from manual URL fetching into a query-driven discovery pipeline with approval and ingestion.

5. A clearer agent/runtime boundary.
   Either simplify the docs to match the current functional architecture, or add a real orchestrator/agent boundary so the docs are no longer aspirational.
