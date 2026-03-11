# PRD Best Practices for AI Agent Consumption — Research Report

Last updated: 2026-03-07

## Purpose

This report synthesizes best practices for writing Product Requirements Documents (PRDs) that are specifically optimized for consumption by AI coding agents. The goal is to inform the construction of a self-prompting PRD generation template that, when fed to a planning agent, produces a complete master execution plan with tracks and slices.

---

## 1. Essential PRD Sections

A world-class PRD is a contract between intent and implementation. Every section exists to eliminate ambiguity and reduce the distance between "what we want" and "what gets built." Below are the sections a complete PRD must include, with rationale for each.

### 1.1 Problem Statement / Opportunity

**What it is:** A crisp description of the problem being solved or the opportunity being captured. This is the "why" of the entire document.

**What it must contain:**
- The current state (what exists today, what's broken or missing)
- The desired future state (what success looks like)
- Who is affected and how severely
- Business justification (revenue impact, user retention, competitive pressure, technical debt cost)
- Evidence supporting the problem (user research, analytics, support tickets, competitive analysis)

**Quality bar:** A reader with no prior context should understand why this work matters after reading this section alone. If the problem statement requires supplementary documents to make sense, it is incomplete.

**Anti-pattern:** "Users want a better experience" — this says nothing. Instead: "43% of users abandon the job application flow at step 3 (resume upload) because the upload widget doesn't support drag-and-drop on mobile, and mobile users represent 67% of our traffic."

### 1.2 Target Users / Personas

**What it is:** A precise description of who will use the feature, segmented by behavior patterns and needs — not demographics.

**What it must contain:**
- Named personas with behavioral descriptions (not just "power user" — describe what they do)
- Primary vs. secondary users (who must be delighted vs. who should not be blocked)
- User context: device, environment, frequency of use, technical sophistication
- Jobs each persona is trying to accomplish
- Current workarounds each persona uses (reveals pain points)

**Quality bar:** An engineer reading this section should be able to answer "would persona X ever use feature Y?" without asking the PM.

**Structure for AI consumption:**
```markdown
#### Persona: {Name}
- **Role:** {description}
- **Goal:** {what they're trying to accomplish}
- **Context:** {device, environment, frequency}
- **Pain points:** {current frustrations}
- **Current workaround:** {how they solve this today}
- **Success looks like:** {observable outcome}
```

### 1.3 User Stories / Jobs-to-Be-Done

**What it is:** Behavioral requirements expressed from the user's perspective. Each story represents a unit of value delivery.

**What it must contain:**
- Stories in standard format: "As a [persona], I want [action] so that [outcome]"
- Acceptance criteria for every story (Given/When/Then or checkbox format)
- Priority level (MoSCoW: Must/Should/Could/Won't)
- Story size estimate (S/M/L) — helps the planning agent create appropriately sized slices
- Dependencies between stories (which stories must land before others)
- Edge cases and error states explicitly called out per story

**Quality bar:** Each story should be independently testable. If you can't write acceptance criteria for it, it's not a story — it's a theme that needs decomposition.

**Structure for AI consumption:**
```markdown
#### US-{NNN}: {Story Title}
- **Priority:** MUST | SHOULD | COULD | WONT
- **Size:** S | M | L
- **Persona:** {persona name}
- **Story:** As a {persona}, I want {action} so that {outcome}.
- **Depends on:** US-{NNN}, US-{NNN} (or "none")
- **Acceptance Criteria:**
  - [ ] GIVEN {precondition} WHEN {action} THEN {result}
  - [ ] GIVEN {precondition} WHEN {action} THEN {result}
- **Edge Cases:**
  - [ ] WHEN {edge condition} THEN {expected behavior}
- **Out of Scope:** {what this story explicitly does NOT cover}
```

### 1.4 Functional Requirements (Features & Behaviors)

**What it is:** A detailed specification of what the system must do, organized by feature area.

**What it must contain:**
- Feature ID and name (stable identifiers for cross-referencing)
- Feature description (what it does, not how it's built)
- Input/output specifications (what goes in, what comes out)
- State transitions (how the system state changes)
- Business rules and validation rules
- Error handling behavior (what happens on each failure mode)
- Integration points with other features
- Feature flags / rollout strategy if applicable

**Quality bar:** An engineer should be able to implement the feature from this section alone, without needing to reverse-engineer intent from mockups or Slack conversations.

**Key principle:** Describe **behavior**, not implementation. "The system must return search results within 200ms for queries up to 100 characters" is a requirement. "Use Elasticsearch" is an implementation decision (belongs in Technical Constraints if mandated).

### 1.5 Non-Functional Requirements (NFRs)

**What it is:** Quality attributes that constrain how the system behaves under stress, at scale, and across environments.

**Categories that must be addressed:**

#### Performance
- Response time targets (p50, p95, p99) for critical paths
- Throughput targets (requests/sec, concurrent users)
- Resource budgets (memory, CPU, bundle size)
- Cold start constraints (serverless, mobile app launch)

#### Security
- Authentication and authorization model
- Data classification (PII, PHI, financial data)
- Encryption requirements (at rest, in transit)
- Input validation and sanitization rules
- Rate limiting and abuse prevention
- Compliance requirements (GDPR, SOC2, HIPAA)
- Secrets management approach

#### Scalability
- Expected load ranges (current, 6-month, 2-year)
- Horizontal vs. vertical scaling expectations
- Data volume projections (rows, storage, bandwidth)
- Multi-tenancy requirements

#### Reliability
- Uptime targets (SLA/SLO)
- Disaster recovery requirements (RPO, RTO)
- Graceful degradation behavior
- Circuit breaker / fallback behavior

#### Accessibility
- WCAG compliance level target (A, AA, AAA)
- Keyboard navigation requirements
- Screen reader compatibility
- Color contrast ratios
- Focus management rules

#### Observability
- Logging requirements (what to log, log levels, structured format)
- Metrics to emit (custom business metrics, technical metrics)
- Tracing requirements (distributed tracing spans)
- Alerting thresholds

#### Internationalization (if applicable)
- Supported locales
- RTL support requirements
- Date/time/currency formatting

**Quality bar:** Each NFR must be measurable. "The system should be fast" is not an NFR. "Search API p95 latency ≤ 200ms at 500 concurrent users" is.

### 1.6 Technical Constraints / Architecture Decisions

**What it is:** Mandated technical choices that the implementation must respect. These are pre-made decisions, not suggestions.

**What it must contain:**
- Mandated technology stack (language, framework, database, cloud provider)
- Existing system integration requirements (APIs to consume, protocols to support)
- Architectural patterns to follow (monolith, microservices, event-driven, etc.)
- Coding standards and conventions already in place
- Build and deployment pipeline constraints
- Backward compatibility requirements
- Migration constraints (zero-downtime, data migration strategy)
- Third-party service constraints (vendor lock-in, licensing, cost limits)

**Quality bar:** If a constraint exists, it must include the reason. "Must use PostgreSQL" is incomplete. "Must use PostgreSQL because the existing user data store is PostgreSQL and a migration is out of scope" gives the implementing agent enough context to make good tradeoffs.

**Structure for AI consumption:**
```markdown
#### TC-{NNN}: {Constraint Name}
- **Constraint:** {what is mandated}
- **Reason:** {why this constraint exists}
- **Flexibility:** HARD (non-negotiable) | SOFT (prefer but can discuss)
- **Impact:** {what this constrains in implementation}
```

### 1.7 Data Models / Schemas

**What it is:** The entities, relationships, and data structures that the system operates on.

**What it must contain:**
- Entity definitions with all fields, types, and constraints
- Relationships between entities (1:1, 1:N, M:N)
- Required vs. optional fields
- Default values
- Validation rules per field (length, format, range, uniqueness)
- Indexes required for query patterns
- Data lifecycle (creation, mutation, soft delete, hard delete, archival)
- Existing schema migrations needed (if modifying existing models)
- Seed data / fixture data requirements

**Quality bar:** An engineer should be able to write the migration file and ORM model from this section.

**Structure for AI consumption:**
```markdown
#### Entity: {EntityName}

| Field | Type | Required | Default | Constraints | Notes |
|---|---|---|---|---|---|
| id | UUID | yes | auto-generated | PK | — |
| name | string | yes | — | max 255 chars, unique per org | indexed |
| status | enum | yes | "draft" | ["draft", "active", "archived"] | — |
| created_at | timestamp | yes | now() | — | immutable after creation |

**Relationships:**
- belongs_to: Organization (org_id FK)
- has_many: Applications
- has_many_through: Tags (via entity_tags join table)
```

### 1.8 API Contracts

**What it is:** The interfaces between system components, including external APIs, internal service boundaries, and event contracts.

**What it must contain:**
- Endpoint path, method, and purpose
- Request schema (headers, path params, query params, body)
- Response schema (success and error shapes)
- Authentication/authorization requirements per endpoint
- Rate limiting per endpoint
- Pagination strategy
- Versioning strategy
- Idempotency requirements
- Webhook/event contracts (if event-driven)

**Quality bar:** A frontend engineer and a backend engineer should be able to work in parallel using only this section as their contract.

**Structure for AI consumption:**
```markdown
#### API-{NNN}: {Endpoint Name}
- **Method:** GET | POST | PUT | PATCH | DELETE
- **Path:** /api/v1/{resource}
- **Auth:** required | optional | none
- **Rate limit:** {N} req/min per {user | IP | API key}

**Request:**
```json
{
  "field_name": "type — description (required|optional, default: X)"
}
```

**Response (200):**
```json
{
  "data": { ... },
  "meta": { "page": 1, "total": 100 }
}
```

**Error Responses:**
- 400: { "error": "validation_error", "details": [...] }
- 401: { "error": "unauthorized" }
- 404: { "error": "not_found" }
- 429: { "error": "rate_limited", "retry_after": 60 }
```

### 1.9 UI/UX Requirements and User Flows

**What it is:** How the user interacts with the system, including navigation, state transitions, and visual requirements.

**What it must contain:**
- User flow diagrams (described textually or as state machines for AI consumption)
- Screen/view inventory (list of all screens/views with purpose)
- Component hierarchy (what components exist on each screen)
- Interaction specifications (click, hover, drag, swipe, keyboard)
- State management (loading, empty, error, success states for each view)
- Form validation rules (inline, on-submit, field-level)
- Navigation patterns (routing, deep linking, back behavior)
- Responsive behavior (breakpoints, layout changes)
- Animation/transition requirements (if any)
- Design system / component library references

**Quality bar:** A frontend engineer should be able to build the UI without needing to ask "what happens when the user does X?"

**Structure for AI consumption (state machine format):**
```markdown
#### Flow: {Flow Name}

States: [idle, loading, loaded, error, empty]

Transitions:
- idle → loading: user clicks "Search"
- loading → loaded: API returns results (count > 0)
- loading → empty: API returns results (count = 0)
- loading → error: API returns error or timeout (> 5s)
- error → loading: user clicks "Retry"
- loaded → loading: user changes filter

Each state renders:
- idle: search form, no results area
- loading: search form (disabled), skeleton loader
- loaded: search form, results list, pagination
- empty: search form, empty state illustration + CTA
- error: search form, error banner with retry button
```

### 1.10 Success Metrics / KPIs

**What it is:** How we measure whether this work achieved its goals.

**What it must contain:**
- Primary success metric (the one number that matters most)
- Secondary metrics (supporting indicators)
- Baseline values (current state measurement)
- Target values (what constitutes success)
- Measurement methodology (how and where we measure)
- Timeframe for evaluation
- Guardrail metrics (metrics that must NOT degrade — e.g., page load time shouldn't increase)
- Instrumentation requirements (what events/tracking must be implemented)

**Quality bar:** After launch, the team should be able to look at a dashboard and answer "did this work?" without debate about methodology.

### 1.11 Scope Boundaries (In/Out of Scope)

**What it is:** Explicit fences around what this work includes and excludes.

**What it must contain:**
- In-scope items (enumerated, specific)
- Out-of-scope items (enumerated, with brief reason for exclusion)
- Deferred items (out of scope now, but planned for future — prevents scope creep from "we'll get to it")
- Scope change process (how does new scope get added? Who approves?)

**Quality bar:** If a developer asks "should I build X?", this section should answer it without ambiguity.

**Why this matters for AI agents:** Without explicit scope boundaries, AI agents will either over-build (implementing everything they can infer) or under-build (stopping at the minimum interpretation). Explicit boundaries give the agent permission to say "this is not my job" for out-of-scope work.

### 1.12 Assumptions and Dependencies

**What it is:** Conditions that are assumed true and external dependencies that must be satisfied.

**What it must contain:**
- Technical assumptions (existing infrastructure, available services, data availability)
- Business assumptions (user behavior, market conditions, regulatory status)
- External dependencies (third-party APIs, other team deliverables, vendor timelines)
- Internal dependencies (other features that must ship first, shared component availability)
- Assumption validation plan (how and when will assumptions be tested?)
- Fallback if dependency is not met (what do we do if X doesn't deliver on time?)

**Quality bar:** Each assumption should be something that could be falsified. "Users will like this" is not an assumption — it's a hope. "At least 30% of current mobile users will use the swipe gesture" is testable.

### 1.13 Risks and Mitigations

**What it is:** Known risks to the project, their likelihood, impact, and planned mitigations.

**What it must contain:**
- Risk ID and description
- Likelihood (High / Medium / Low)
- Impact (High / Medium / Low)
- Mitigation strategy (how we prevent or reduce the risk)
- Contingency plan (what we do if the risk materializes despite mitigation)
- Risk owner (who monitors and acts on this risk)

**Structure for AI consumption:**
```markdown
| Risk ID | Description | Likelihood | Impact | Mitigation | Contingency |
|---|---|---|---|---|---|
| R-001 | Third-party API rate limits may be too low for peak usage | Medium | High | Implement caching layer + request queuing | Fallback to cached results with staleness indicator |
```

### 1.14 Release Criteria / Definition of Done

**What it is:** The gate criteria that must ALL be satisfied before the work is considered shippable.

**What it must contain:**
- Functional completeness criteria (all MUST stories implemented and tested)
- Quality criteria (test coverage thresholds, zero critical bugs, accessibility audit passed)
- Performance criteria (load test results within NFR targets)
- Security criteria (security review completed, no open critical/high findings)
- Documentation criteria (API docs updated, runbook written, architecture decision records filed)
- Operational criteria (monitoring dashboards live, alerts configured, rollback plan tested)
- Stakeholder sign-off requirements

**Quality bar:** This section should be a checklist that a CI/CD pipeline could enforce. No subjective criteria — everything measurable.

### 1.15 Glossary

**What it is:** Domain-specific terms and their precise definitions within this project's context.

**What it must contain:**
- Every domain term used in the PRD that has project-specific meaning
- Every acronym used in the PRD, expanded
- Disambiguation for terms that could mean different things in different contexts
- Technical terms that cross team boundaries (e.g., "event" means one thing to frontend, another to backend)

**Why this matters for AI agents:** AI agents operate on token-level semantics. If "job" means both "a background processing task" and "a job listing a user applies to" in different parts of the PRD, the agent will conflate them. The glossary prevents this.

---

## 2. PRD Anti-Patterns

### 2.1 Being Too Vague

**Symptom:** Requirements that could mean anything.

**Examples:**
- "The system should be user-friendly" — what does this mean? Keyboard navigation? Reduced clicks? Tooltips?
- "Performance should be good" — good compared to what? Under what load?
- "Handle errors gracefully" — show a toast? Retry? Log and continue? Redirect?

**Fix:** Every requirement must pass the "test it" test. If you can't write a test for it, it's not specific enough. Convert vague requirements into measurable acceptance criteria.

### 2.2 Being Too Prescriptive

**Symptom:** PRD dictates implementation details instead of behavior.

**Examples:**
- "Use a Redux store with a normalized entity adapter for the jobs slice" — this is implementation, not a requirement
- "Create a `useJobSearch` hook that debounces input by 300ms" — this over-constrains the solution
- "The database should use a B-tree index on the `created_at` column" — this is an optimization decision, not a requirement

**Fix:** Describe what the system must do, not how. The PRD should say "Search results must update within 500ms of the user stopping typing." The engineer (or AI agent) decides that debouncing at 300ms achieves this. Exception: when a specific implementation is mandated by a technical constraint (e.g., "must use the existing gRPC service"), document it in Technical Constraints with a reason.

**The sweet spot:** Requirements should be specific enough to test but flexible enough to allow implementation creativity. Constrain the **what** and the **quality bar**, not the **how**.

### 2.3 Missing Edge Cases

**Symptom:** PRD only describes the happy path.

**Common blind spots:**
- Empty states (no data, no results, no permissions)
- Boundary values (0, 1, max, max+1)
- Concurrent operations (two users editing the same thing)
- Network failures (offline, timeout, partial response)
- Permission boundaries (what happens when a user tries something they can't do?)
- Data format edge cases (Unicode, RTL text, extremely long strings, special characters)
- Time-based edge cases (timezone boundaries, DST transitions, leap years)
- State corruption (what if the user refreshes mid-operation?)

**Fix:** For every user story, ask: "What if it fails? What if it's empty? What if there's too much? What if two users do it at the same time? What if the user does it in a weird order?" Document these as explicit edge case acceptance criteria.

### 2.4 Conflicting Requirements

**Symptom:** Two requirements contradict each other, and the PRD doesn't acknowledge or resolve the conflict.

**Examples:**
- "All API responses must include full entity details" + "API responses must be under 1KB" — these conflict for entities with many fields
- "Users must be able to delete their account immediately" + "We must retain user data for 7 years for compliance" — these require a nuanced reconciliation (soft delete + anonymization)
- "The app must work offline" + "All data must be real-time" — these need a conflict resolution strategy (optimistic updates, sync queue)

**Fix:** Before finalizing the PRD, create a requirements traceability matrix. For each pair of requirements that touch the same domain, verify they don't conflict. When tensions exist, document the resolution strategy explicitly.

### 2.5 No Prioritization

**Symptom:** Everything is P0. Or nothing is prioritized at all.

**Why it matters:** Without prioritization, an AI agent has no way to make tradeoff decisions. If implementation gets complex, should the agent simplify feature A or feature B? Without priority signals, it will make arbitrary choices.

**Fix:** Use MoSCoW (Must/Should/Could/Won't) or a numbered priority system. Rules:
- MUST: The release is a failure without this. No more than 60% of scope should be MUST.
- SHOULD: Important but the release can ship without it.
- COULD: Nice-to-have. Build it if there's time and no risk to MUST items.
- WON'T: Explicitly excluded. Prevents scope creep.

**For AI agents:** Priority determines slice ordering. MUST items become early tracks; COULD items become late tracks or are deferred entirely.

### 2.6 Missing Acceptance Criteria

**Symptom:** Stories exist but have no testable criteria for "done."

**Why it matters for AI agents:** Without acceptance criteria, the AI agent must invent its own definition of done. It will either over-build (adding features it imagines are needed) or under-build (implementing the bare minimum interpretation). Acceptance criteria are the contract the agent implements against.

**Fix:** Every story gets Given/When/Then criteria or a checklist. No exceptions. If a story can't have acceptance criteria, it's not a story — it's a spike or research task (which should have its own "done" definition: "Produce a recommendation document covering X, Y, Z").

### 2.7 Assuming Undocumented Context

**Symptom:** The PRD makes sense to the author but not to someone (or something) reading it for the first time.

**Common assumptions that break AI agents:**
- "The auth system" — which auth system? How does it work? What tokens does it use?
- "The existing search" — what search? What does it query? What does it return?
- "Standard pagination" — cursor-based or offset-based? What's the default page size?
- "Our design system" — which components are available? What are the naming conventions?
- Referring to decisions made in Slack or meetings without documenting them

**Fix:** Write the PRD as if the reader just joined the company today. Every reference to existing systems should include enough context to understand the interface without reading the source code. For AI agents, this is literal — they have no institutional memory.

### 2.8 Mixing Problem and Solution

**Symptom:** The problem statement is actually a solution description.

**Example:** "We need to add a Redis cache layer" — this is a solution. The problem is "API response times for the job listing endpoint are 2.3s at p95, exceeding our 500ms target." Redis might be the right solution, but the PRD should separate problem from solution so the implementing agent can validate that the solution actually addresses the problem.

### 2.9 No Versioning or Change History

**Symptom:** The PRD is a living document that changes without any record of what changed.

**Fix:** Include a change log at the top. Each entry: date, what changed, why, who approved. For AI agents, this prevents "I implemented the old version" errors.

---

## 3. PRD for AI Agent Consumption

This section addresses what makes a PRD optimally parseable and actionable for an AI coding agent that will consume it to produce a master execution plan.

### 3.1 Structured Format Requirements

**Use markdown with consistent, hierarchical headings.** AI agents parse structure through heading levels. Inconsistent heading hierarchies (mixing `##` and `####` at the same conceptual level) confuse section boundary detection.

**Rules:**
1. `#` — document title (exactly one)
2. `##` — major sections (Problem, Users, Stories, Requirements, etc.)
3. `###` — subsections (individual features, individual personas)
4. `####` — items within subsections (individual stories, individual API endpoints)
5. Never skip heading levels (no `##` → `####` without `###`)

**Use stable, prefixed identifiers for every referenceable item:**
- User stories: `US-001`, `US-002`
- Functional requirements: `FR-001`, `FR-002`
- Non-functional requirements: `NFR-001`, `NFR-002`
- Technical constraints: `TC-001`, `TC-002`
- API endpoints: `API-001`, `API-002`
- Data entities: `ENT-001`, `ENT-002`
- Risks: `R-001`, `R-002`

**Why:** These IDs allow the planning agent to create traceability links (e.g., "Track 3 implements US-005, US-006, and FR-012") and dependency graphs.

### 3.2 Machine-Readable Acceptance Criteria

**Format acceptance criteria as checkboxes with structured Given/When/Then:**

```markdown
- [ ] **AC-001:** GIVEN a logged-in user with role "applicant" WHEN they submit a job application with all required fields THEN the application is created with status "submitted" AND the user receives a confirmation email within 60 seconds
- [ ] **AC-002:** GIVEN a logged-in user with role "applicant" WHEN they submit a job application with a missing required field THEN the API returns 400 with field-level validation errors AND no application is created
```

**Why checkboxes:** The planning agent can map checkboxes to verification steps. Each checkbox becomes a test case in the execution plan.

**Why IDs on criteria:** Allows the execution plan to reference specific acceptance criteria per slice: "Slice 2.3 implements AC-001 through AC-004."

### 3.3 Explicit Scope Boundaries

**Use two clearly labeled lists:**

```markdown
## Scope

### In Scope
- [ ] Job search with text query and filters (location, salary range, job type)
- [ ] Job detail view with full description and apply button
- [ ] Swipe-based job browsing (right = save, left = skip)

### Out of Scope
- Employer-side job posting interface (deferred to Phase 2)
- Payment processing for premium listings (deferred to Phase 3)
- Mobile push notifications (deferred — requires native app decision)

### Explicitly Excluded (Will Not Build)
- Social features (comments, likes on job postings)
- Built-in messaging between applicants and employers
```

**Why three categories:** "Out of scope" and "Explicitly excluded" are different. Out-of-scope items may come later; excluded items are architectural decisions. AI agents need to know the difference to avoid accidentally building toward excluded features.

### 3.4 Unambiguous Language Patterns

**Use RFC 2119 keywords consistently:**
- **MUST / MUST NOT** — absolute requirements
- **SHOULD / SHOULD NOT** — strong recommendations (deviate only with documented reason)
- **MAY** — truly optional

**Avoid these words without quantification:**
- ❌ "fast" → ✅ "responds within 200ms at p95"
- ❌ "secure" → ✅ "all PII fields encrypted at rest using AES-256"
- ❌ "scalable" → ✅ "handles 10,000 concurrent users without degradation"
- ❌ "user-friendly" → ✅ "achieves SUS score ≥ 80 in usability testing"
- ❌ "handles errors" → ✅ "on API error: displays error banner with message, logs error with request ID, offers retry button"
- ❌ "supports mobile" → ✅ "responsive layout at 320px, 768px, 1024px, 1440px breakpoints"

**Use active voice and specify the subject:**
- ❌ "The data should be validated" — by whom? The client? The server? Both?
- ✅ "The API server MUST validate all input fields before processing"

### 3.5 Mapping Requirements to Implementation Tasks

**Structure requirements so they decompose naturally into implementation slices:**

1. **Group by feature area, not by layer.** A "Search" feature group contains its API endpoint, its data query, its UI component, and its tests. This maps to a vertical slice in the execution plan.

2. **Include dependency signals.** If Feature B requires Feature A's data model, say so explicitly: "Depends on: ENT-003 (Job entity from FR-002)."

3. **Order by implementation dependency, not by document aesthetics.** Put foundation features (auth, data models, shared components) before features that depend on them.

4. **Size indicators.** Tag each feature group with an estimated size (S/M/L/XL). This helps the planning agent create appropriately scoped slices:
   - **S:** Single file change, < 100 lines, no new dependencies
   - **M:** 2-5 files, new component or endpoint, straightforward logic
   - **L:** 5-15 files, new subsystem, complex business logic, needs tests
   - **XL:** Full new domain, cross-cutting concerns, architectural changes

5. **Implementation hints (optional).** If the codebase has established patterns, reference them: "Follow the pattern established in `src/features/auth/` for feature module structure." This is not prescriptive (it doesn't dictate the implementation) — it's a pointer to existing conventions.

### 3.6 Structuring PRD → Master Plan with Tracks/Slices

**The PRD should organize requirements into natural execution tracks:**

```
PRD Feature Group → Master Plan Track → Child Plan with Slices
```

**Recommended PRD organization that maps to tracks:**

```markdown
## Features

### Track: Foundation (must be first)
- Data models and migrations
- Authentication/authorization setup
- Shared utilities and configuration
- Base UI component setup

### Track: Core Feature A
- US-001: {story}
- US-002: {story}
- FR-001 through FR-005

### Track: Core Feature B (depends on Foundation)
- US-003: {story}
- US-004: {story}
- FR-006 through FR-010

### Track: Integration & Polish (depends on A and B)
- Cross-feature interactions
- Error handling hardening
- Performance optimization
- Accessibility audit items
```

**Each track should have:**
- Clear entry criteria (what must be true before this track starts)
- Clear exit criteria (what must be true for this track to be "done")
- A list of the user stories and requirements it implements
- An estimated slice count (how many PR-sized chunks)

**The planning agent uses this structure to:**
1. Create one child plan per track
2. Decompose each track into ordered slices
3. Establish cross-track dependencies
4. Assign verification criteria per slice

### 3.7 Self-Contained Context Blocks

**AI agents operate with limited context windows.** The PRD should be structured so that each section is as self-contained as possible.

**Rules:**
- When a section references another section, include a brief inline summary rather than just "see Section 3.2"
- Define terms where they're first used, not just in the glossary
- Repeat critical constraints in every section they apply to (e.g., if auth is required, mention it in every API endpoint, not just in the Security section)
- Use consistent naming — if the entity is called "Job" in the data model, don't call it "Listing" in the API section and "Position" in the UI section

---

## 4. PRD Completeness Checklist

Use this checklist to verify a PRD is complete before handing it to a planning agent. Every item must be checked or explicitly marked N/A with a reason.

### Document Structure
- [ ] Document has exactly one `#` title
- [ ] All sections use consistent heading hierarchy (`##` → `###` → `####`)
- [ ] All referenceable items have stable prefixed IDs (US-, FR-, NFR-, TC-, API-, ENT-, R-)
- [ ] Change log / version history is present
- [ ] Glossary defines all domain-specific terms and acronyms

### Problem & Context
- [ ] Problem statement describes current state, desired state, and who is affected
- [ ] Business justification is included with evidence (not just assertion)
- [ ] Target users/personas are defined with behavioral descriptions
- [ ] Each persona has: role, goal, context, pain points, success criteria

### Requirements Completeness
- [ ] Every user story has: persona, action, outcome, priority (MoSCoW), size estimate
- [ ] Every user story has at least one acceptance criterion in Given/When/Then format
- [ ] Every user story has edge cases enumerated
- [ ] Functional requirements cover: inputs, outputs, state transitions, error handling
- [ ] All MUST-priority stories have acceptance criteria (no exceptions)
- [ ] Dependencies between stories are explicitly documented

### Non-Functional Requirements
- [ ] Performance targets specified with percentiles and load conditions
- [ ] Security requirements specified (auth, encryption, data classification, compliance)
- [ ] Scalability expectations documented with projected load numbers
- [ ] Reliability targets specified (uptime, RPO, RTO)
- [ ] Accessibility requirements specified with WCAG level
- [ ] Observability requirements specified (logging, metrics, tracing, alerting)

### Technical Specification
- [ ] Technical constraints documented with reasons and flexibility level
- [ ] Data models include: all fields, types, constraints, relationships, validation rules
- [ ] API contracts include: method, path, auth, request schema, response schema, error responses
- [ ] UI/UX flows described with states and transitions (not just happy path)
- [ ] All screens/views inventoried with their states (loading, empty, error, success)

### Scope & Prioritization
- [ ] In-scope items enumerated
- [ ] Out-of-scope items enumerated with reasons
- [ ] Explicitly excluded items documented
- [ ] No more than 60% of stories are MUST priority
- [ ] At least one story is WON'T (evidence of conscious scoping)

### Risk & Dependencies
- [ ] Assumptions listed and each is falsifiable
- [ ] External dependencies identified with fallback plans
- [ ] Risks documented with likelihood, impact, mitigation, and contingency
- [ ] Assumption validation plan exists

### Release & Success
- [ ] Definition of done is a measurable checklist
- [ ] Success metrics have baseline values and targets
- [ ] Guardrail metrics identified (metrics that must not degrade)
- [ ] Instrumentation requirements documented for success measurement

### AI-Agent Readiness
- [ ] All acceptance criteria use Given/When/Then format with checkboxes
- [ ] Requirements grouped by feature area (vertical slices), not by layer
- [ ] Feature groups annotated with size estimates (S/M/L/XL)
- [ ] Track dependencies explicitly documented ("Track B depends on Track A because...")
- [ ] Each track has entry criteria and exit criteria
- [ ] RFC 2119 keywords used consistently (MUST/SHOULD/MAY)
- [ ] No vague adjectives without quantification (fast, secure, scalable, user-friendly)
- [ ] Every external system reference includes enough context to understand the interface
- [ ] PRD is self-contained — no critical information exists only in external documents
- [ ] Feature groups map cleanly to execution tracks (Foundation → Core A → Core B → Polish)

---

## 5. Research Methodology for Auto-Generating a PRD

When an AI agent is tasked with auto-generating a PRD for an existing codebase, it must systematically research the following areas to produce an accurate and complete document.

### 5.1 Codebase Structure & Tech Stack

**What to investigate:**
- Directory structure and module organization patterns
- Language(s) and framework(s) in use (check package files, build configs, language-specific markers)
- Monorepo vs. polyrepo structure
- Frontend/backend separation strategy
- Shared code patterns (shared types, shared utilities)

**How to investigate:**
```
- Read directory tree (2-3 levels deep)
- Read package.json / requirements.txt / go.mod / Cargo.toml / build.gradle
- Read framework config files (next.config.js, vite.config.ts, tsconfig.json, pyproject.toml)
- Read Docker/docker-compose files for service topology
- Read CI/CD configs (.github/workflows/, Jenkinsfile, .gitlab-ci.yml)
```

**What to extract:**
- Language version constraints
- Framework and major library versions
- Build tooling (bundler, compiler, test runner)
- Deployment target (serverless, containers, VMs, static hosting)

### 5.2 Existing Features vs. Planned Features

**What to investigate:**
- What the application currently does (working features)
- What's partially built (feature flags, commented-out code, incomplete modules)
- What's planned but not started (issues, project boards, roadmap docs)

**How to investigate:**
```
- Read README.md (often describes features and roadmap)
- Read CHANGELOG.md (recent feature additions)
- Scan for feature flag configurations
- Search for TODO, FIXME, HACK, XXX comments in source
- Check GitHub Issues (open issues tagged as feature requests or enhancements)
- Check GitHub Projects / Milestones for planned work
- Look for docs/ directory with specifications or design docs
- Look for ADRs (Architecture Decision Records)
```

**What to extract:**
- Inventory of working features (verified by tests or clear implementation)
- Inventory of in-progress features (partially implemented)
- Inventory of planned features (documented but not started)
- Known technical debt items

### 5.3 README, Docs, Comments, TODOs

**What to investigate:**
- All user-facing documentation
- All developer-facing documentation
- Inline code documentation (especially at module/class/function level)
- TODO/FIXME markers indicating incomplete work

**How to investigate:**
```
- Read README.md thoroughly
- Read all files in docs/ directory
- Read CONTRIBUTING.md, ARCHITECTURE.md if they exist
- Search for docstrings/JSDoc/pydoc at module and class level
- Aggregate all TODO/FIXME/HACK/XXX comments with file locations
- Read API documentation if auto-generated (Swagger/OpenAPI specs)
```

**What to extract:**
- Product description and positioning
- Setup and configuration instructions (reveals technical constraints)
- Architecture overview (if documented)
- Known limitations (often documented in README)
- Development workflow and conventions
- List of incomplete work items from code comments

### 5.4 Package Dependencies & Their Purposes

**What to investigate:**
- All direct dependencies and their roles
- Dev dependencies (test frameworks, linters, build tools)
- Dependency version constraints (pinned, ranges, latest)
- Optional/peer dependencies

**How to investigate:**
```
- Read package.json (dependencies + devDependencies)
- Read requirements.txt / Pipfile / poetry.lock
- Read go.mod / go.sum
- Read Cargo.toml
- For each non-obvious dependency, check its purpose (npm page, PyPI page, crate docs)
- Check for lockfiles (package-lock.json, yarn.lock, poetry.lock) to understand exact versions
```

**What to extract:**
- Categorized dependency list: UI framework, state management, routing, HTTP client, ORM, testing, linting, etc.
- Unused dependencies (installed but not imported anywhere)
- Outdated dependencies with potential security implications
- Dependencies that constrain architecture decisions (e.g., choosing Prisma constrains database operations)

### 5.5 Database Schemas / Models

**What to investigate:**
- All data models / entities in the system
- Relationships between entities
- Database type and configuration
- Migration history

**How to investigate:**
```
- Read ORM model files (models.py, schema.prisma, *.entity.ts, etc.)
- Read migration files (understand schema evolution)
- Read database configuration (connection strings, pool sizes — sanitize secrets!)
- Read seed data files (reveals expected data patterns)
- Check for multiple databases (primary DB, cache, search index, message queue)
- Look for schema validation (Zod, Joi, Pydantic, JSON Schema files)
```

**What to extract:**
- Complete entity inventory with fields, types, and relationships
- Indexes and performance-critical query patterns
- Data validation rules already implemented
- Current migration state
- Soft delete vs. hard delete patterns

### 5.6 API Routes & Contracts

**What to investigate:**
- All exposed API endpoints
- Request/response shapes
- Authentication and authorization patterns
- Middleware chain
- Error handling patterns

**How to investigate:**
```
- Read route definition files (routes.py, router.ts, controllers/)
- Read middleware configuration (auth middleware, CORS, rate limiting)
- Read API validation schemas (request/response validators)
- Read OpenAPI/Swagger specs if they exist
- Read API tests (reveal expected request/response shapes)
- Search for fetch/axios/http client calls in frontend (reveals API consumption patterns)
- Look for API versioning patterns (/api/v1/, /api/v2/)
```

**What to extract:**
- Complete route inventory: method, path, auth requirements, request/response shapes
- Authentication flow (login, token refresh, session management)
- Authorization model (roles, permissions, resource-level access control)
- Error response format and error codes
- Pagination strategy
- Rate limiting configuration

### 5.7 Test Coverage & Gaps

**What to investigate:**
- What testing frameworks are configured
- What types of tests exist (unit, integration, E2E, visual regression)
- What's tested vs. what's not
- Test quality (meaningful assertions vs. "doesn't throw")

**How to investigate:**
```
- Read test configuration (jest.config, pytest.ini, vitest.config, cypress.config)
- List all test files and categorize by type
- Run test coverage report (if coverage tooling exists)
- Read a sample of tests to assess quality (do they test behavior or implementation?)
- Search for skipped/disabled tests (.skip, @skip, xtest, xit) — these often indicate known issues
- Check CI config for which tests run on which triggers
```

**What to extract:**
- Test framework and runner configuration
- Coverage percentage (overall and by module)
- Modules with zero or near-zero coverage
- Test patterns in use (mocking strategy, fixture patterns, test utilities)
- Known test gaps (untested features, skipped tests)
- E2E test inventory (what user flows are covered end-to-end?)

### 5.8 User-Facing Configuration

**What to investigate:**
- Environment variables the application uses
- Configuration files users must maintain
- Feature flags and their current states
- Deployment-specific configuration

**How to investigate:**
```
- Read .env.example / .env.template files
- Read configuration loading code (config.ts, settings.py, etc.)
- Search for process.env / os.environ / os.Getenv references
- Read Docker/docker-compose environment sections
- Read deployment manifests (Kubernetes YAML, Terraform, CloudFormation)
- Check for configuration validation (what happens if a required var is missing?)
```

**What to extract:**
- Complete list of configuration variables with purpose and required/optional status
- Default values and valid ranges
- Configuration that affects behavior (feature flags, mode switches)
- Secrets that must be provided (without documenting actual values)
- Environment-specific configuration (dev, staging, production differences)

### 5.9 Deployment Setup

**What to investigate:**
- How the application is built and deployed
- Infrastructure requirements
- CI/CD pipeline configuration
- Monitoring and observability setup

**How to investigate:**
```
- Read Dockerfile(s) and docker-compose.yml
- Read CI/CD configs (.github/workflows/, .circleci/, Jenkinsfile)
- Read deployment scripts (deploy.sh, Makefile targets)
- Read infrastructure-as-code (Terraform, CloudFormation, Pulumi)
- Read monitoring configuration (Datadog, New Relic, Prometheus configs)
- Check for health check endpoints
- Check for database migration strategy in deployment
```

**What to extract:**
- Build process and artifacts
- Deployment target and strategy (rolling, blue-green, canary)
- Infrastructure dependencies (managed services, external APIs)
- Environment management (how many environments, how they differ)
- Rollback capabilities
- Monitoring and alerting already in place

### 5.10 Research Output Format

The research phase should produce a structured artifact that feeds directly into PRD generation:

```markdown
## Codebase Research Summary

### Tech Stack
- **Language:** {language} {version}
- **Frontend:** {framework} {version}
- **Backend:** {framework} {version}
- **Database:** {type} {version}
- **Deployment:** {platform}

### Current Feature Inventory
| Feature | Status | Test Coverage | Notes |
|---|---|---|---|
| {feature} | working / partial / planned | high / low / none | {notes} |

### Data Model Summary
| Entity | Fields | Relationships | Notes |
|---|---|---|---|
| {entity} | {count} fields | {relationships} | {notes} |

### API Surface
| Endpoint | Method | Auth | Status |
|---|---|---|---|
| /api/v1/{path} | GET/POST/... | required/none | working / stub |

### Known Issues & Technical Debt
| Source | Description | Severity | Location |
|---|---|---|---|
| TODO comment | {description} | {high/med/low} | {file:line} |
| Missing tests | {description} | {high/med/low} | {module} |

### Configuration Surface
| Variable | Purpose | Required | Default |
|---|---|---|---|
| {VAR_NAME} | {purpose} | yes/no | {default} |

### Open Questions (Require Human Input)
1. {Question that cannot be answered from code alone}
2. {Business decision that must be made}
```

---

## 6. Summary: The PRD Quality Hierarchy

A PRD consumed by an AI agent must satisfy these quality levels, in order:

1. **Parseable** — Consistent markdown structure, stable IDs, hierarchical headings
2. **Complete** — All sections present, all acceptance criteria written, all edge cases documented
3. **Unambiguous** — RFC 2119 keywords, quantified metrics, no vague adjectives
4. **Self-contained** — No critical context exists outside the document
5. **Actionable** — Requirements map to vertical slices, dependencies are explicit, priorities are assigned
6. **Traceable** — Every requirement has an ID, every track references its requirements, every acceptance criterion maps to a test

A PRD that achieves all six levels can be consumed by a planning agent to produce a master execution plan that an implementing agent can execute with minimal human intervention.

---

## 7. Recommended PRD Section Order for AI Consumption

The optimal reading order for an AI planning agent differs from a traditional PRD because the agent needs context before it encounters requirements:

1. **Glossary** (read first — establishes vocabulary)
2. **Problem Statement** (establishes why)
3. **Target Users / Personas** (establishes who)
4. **Scope Boundaries** (establishes fences before requirements)
5. **Technical Constraints** (establishes non-negotiable implementation boundaries)
6. **Data Models** (establishes the nouns)
7. **User Stories** (establishes the verbs — what users do with the nouns)
8. **Functional Requirements** (detailed behavior specifications)
9. **API Contracts** (interface specifications)
10. **UI/UX Requirements** (presentation specifications)
11. **Non-Functional Requirements** (quality constraints)
12. **Assumptions & Dependencies** (what must be true)
13. **Risks & Mitigations** (what might go wrong)
14. **Success Metrics** (how we measure)
15. **Release Criteria** (when we ship)

This order ensures the agent has full context before encountering detailed requirements, reducing the chance of misinterpretation.
