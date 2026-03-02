# docs/PRODUCT_SPEC.md

## Product vision
Coleonri is a tutor that optimizes for **deep learning**, not quick dopamine.

Core principles:
- **Socratic by default** (no brainrot “just give me the answer”)
- **Mastery gating** unlocks direct summaries/explanations
- **Level-up quizzes** are the main progression mechanic
- Graph + “I’m feeling lucky” encourages **breadth + exploration**
- Answers should be **grounded** in the user’s materials by default (hybrid), with a strict toggle

---

## Key user features

### 1) Chat tutor (default Socratic)
- The tutor primarily responds with:
  - guiding questions
  - hints
  - prompting steps
  - checks for understanding
- The tutor may provide short explanations, but avoids giving final “easy answers” when mastery is not achieved.

### 2) Mastery gating (learned vs not learned)
For a given concept/topic:
- If **not learned**: tutor must remain Socratic and encourage practice/level-up.
- If **learned**: user may request direct outputs:
  - summaries
  - cheat sheets
  - straightforward explanations

### 3) Level-up quiz card (progression)
- The system can suggest a level-up quiz when the user seems ready.
- The user can also explicitly summon it.

**Card behavior:**
- Display 5–10 questions in a single card UI.
- User answers all questions and submits once.
- Mixed grading:
  - MCQ items are graded deterministically with per-choice explanations.
  - Short-answer items are graded by LLM using a strict rubric schema.
- Grading context:
  - Persist a generation-time context snapshot per item and reuse it during grading.
  - This keeps grading aligned with the exact context used when the quiz was created.
- Mastery is updated.
- Tutor returns per-item feedback plus an overall feedback summary and next steps.

### 4) Practice mode (non-leveling)
From the graph UI:
- Select a node → generate:
  - flashcards
  - mini quizzes
These do **not** change mastery status to learned. They are practice only.
- Mini quizzes are bounded to **3–6** items and must include at least one `short_answer` and one `mcq`.
- Practice quiz generation is resilient to malformed model output:
  - normalize common short-answer payload shape issues (for example, `rubric_keywords`)
  - regenerate up to **3 attempts** before returning a validation error
- Practice submissions return score + feedback but never mutate mastery state.

#### 4a) Unified flashcard stack
- All flashcard runs for a concept are merged into a single reviewable stack.
- "Generate more" appends to the existing stack rather than creating a new run.
- When all cards for a concept are exhausted, the generate button is disabled with an exhaustion reason.

#### 4b) Quiz history with retry
- Past practice quizzes are listed with date and score.
- Users can open a past quiz to review answers and feedback.
- A retry button resets answers and lets the user re-attempt (practice quizzes only, not level-up).

### 5) Graph UI (progress + exploration)
Users can:
- view their concept graph (canonical)
- inspect a node’s description
- see adjacent nodes
- trigger practice tools from a node
- navigate to an active chat session from the graph detail panel (graph-to-chat navigation)

#### 5a) Rendering & interaction
- Graph is rendered with **Sigma.js** (WebGL) backed by a **graphology** data model, replacing the earlier D3 force simulation.
- Default layout: **ForceAtlas2** (via `graphology-layout-forceatlas2` web worker). Users can switch between ForceAtlas2 and circular layouts.
- Camera controls: zoom-to-fit, zoom-in/out, and reset buttons. Mouse wheel zoom and drag-to-pan supported.

#### 5b) Search & filtering
- **MiniSearch** fuzzy search over node labels with instant highlight and camera focus.
- Expand/prune controls to add neighbor nodes or remove leaf nodes from the visible subgraph.

### 6) “I’m feeling lucky”
A button that suggests:
- **Adjacent learning**: topics within k hops of current node
- **Wildcard**: something new (optionally random, but still relevant to the workspace domain)

### 7) Onboarding confirmation step
- When a user selects a topic chip during onboarding, a confirmation card is shown ("Ready to learn about X? → Start learning") instead of auto-populating the chat textbox.
- This prevents accidental topic starts and gives the user an explicit opt-in.

### 8) Streaming status (replace-mode)
- During tutor response generation, a single-line status indicator shows the current processing step (e.g., "Retrieving evidence…", "Composing response…").
- Each new status replaces the previous one (ChatGPT-style) rather than appending to a growing log.

### 9) Dev stats toggle
- A frontend-only toggle (persisted via `localStorage`) to show or hide generation trace metadata (token counts, latency, model) on tutor responses.
- The backend always includes `generation_trace` in the response; visibility is controlled client-side.

### 10) LLM prompt caching
- Tutor and generation prompts are structured to maximize OpenAI prefix caching (stable system message prefix).
- `cached_tokens` is logged in generation traces for observability.

---

## Sources page

### Tier breakdown
- Each document in the knowledge base shows:
  - `ingestion_status` — current processing state
  - `graph_status` — whether graph extraction completed
  - `graph_concept_count` — number of concepts extracted from the document
  - Document summary (generated at ingest time)
- This gives users per-document visibility into how their materials contribute to the knowledge graph.

---

## Learning state machine (per user x concept)
Statuses:
- `locked` → not introduced
- `learning` → introduced but not mastered
- `learned` → completed via level-up criteria

Transitions:
- `locked -> learning`:
  - user asks about it OR it’s suggested by system and user engages
- `learning -> learned`:
  - user completes level-up quiz with passing grade threshold
- `learned -> learning` (optional later):
  - if repeated failures on future assessments (decay/regression)

Mastery fields:
- `score` float 0..1
- `status` enum above
- `updated_at`

Passing criteria (MVP defaults):
- Level-up quiz pass if:
  - overall score >= 0.75 AND
  - no critical misconception flagged by rubric
(Thresholds configurable.)

---

## Answer grounding modes
Default: **Hybrid mode**
- Prefer grounded evidence from user materials.
- If adding general knowledge, label it clearly:
  - “From your notes:” vs “General context:”

Toggle: **Strict grounded mode**
- If evidence is insufficient:
  - refuse / ask user to upload relevant materials
  - or ask clarifying questions to locate the right doc

---

## Tutor response rules (MVP)
When mastery status is NOT learned:
- avoid giving final answers directly
- prefer question-first responses:
  - “What do you think happens when…?”
  - “Try deriving step 1: …”
- can provide small scaffolding snippets, not full solutions
- may recommend the Level-up quiz

When mastery status is learned:
- can provide direct summaries and explanations
- still cites sources when possible

---

## Core user flows

### Flow A: Chat learning
1) user asks question
2) system retrieves evidence
3) tutor answers Socratically (if not learned)
4) user engages
5) system suggests level-up
6) user completes quiz → mastery updates

### Flow B: Level-up quiz card
1) user starts level-up
2) quiz generated + shown as card
3) user submits answers
4) graded + feedback
5) mastery updated + direct mode unlocked for that concept

### Flow C: Graph exploration
1) user opens graph view
2) selects node
3) generates flashcards or practice quiz
4) returns to chat with practice feedback

### Flow D: I’m feeling lucky
1) user clicks lucky
2) system chooses adjacent or wildcard topic
3) tutor offers a short hook + learning path + optional quiz

---

## Non-goals (MVP)
- PDF/image crop/zoom perception
- multi-language learning logic
- spaced repetition scheduling (can be phase 2)
- rich course authoring tools

---

## Success metrics (practical)
- % of chat sessions that lead to a level-up attempt
- level-up pass rate over time
- reduction in “give me the answer” attempts (or user satisfaction with Socratic mode)
- graph connectivity and duplicate rate (from GRAPH.md metrics)
