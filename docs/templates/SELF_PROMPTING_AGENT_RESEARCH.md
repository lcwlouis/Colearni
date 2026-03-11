# Self-Prompting, Self-Correcting AI Agent Design: A Comprehensive Report

> **Purpose:** Reference guide for building AI agents that autonomously research codebases, generate structured documents (e.g., PRDs), and iteratively refine their output until convergence.

---

## Table of Contents

1. [Self-Prompting Patterns](#1-self-prompting-patterns)
2. [Self-Correction / Reflection Loops](#2-self-correction--reflection-loops)
3. [Research Agent Patterns](#3-research-agent-patterns)
4. [Output Quality Enforcement](#4-output-quality-enforcement)
5. [Anti-Patterns to Avoid](#5-anti-patterns-to-avoid)
6. [Prompt Engineering for Agent Chains](#6-prompt-engineering-for-agent-chains)
7. [Convergence Protocol Design](#7-convergence-protocol-design)

---

## 1. Self-Prompting Patterns

Self-prompting is the mechanism by which an agent drives itself through a multi-step workflow without external intervention. The agent acts as both the orchestrator and the executor.

### 1.1 Chain-of-Thought Decomposition

Break a complex task into discrete reasoning steps. Each step produces an intermediate artifact that feeds the next.

**Pattern:** Define the full chain upfront, then execute sequentially.

```
TASK: Generate a PRD for the authentication module.

CHAIN:
  Step 1 → Identify all auth-related files in the codebase
  Step 2 → Extract current auth flow (login, signup, token refresh)
  Step 3 → Identify gaps between current implementation and requirements
  Step 4 → Draft PRD sections based on findings
  Step 5 → Cross-validate PRD against codebase evidence
  Step 6 → Finalize and format
```

**Key principle:** Each step must produce a concrete, inspectable artifact — not just "think about X." Force the agent to write down its intermediate findings in a structured format (a list, a table, a JSON object).

**Example prompt snippet:**

```
You are executing Step 2 of 6: Extract Current Auth Flow.

INPUT: The file list from Step 1:
- src/auth/login.ts
- src/auth/signup.ts
- src/auth/middleware.ts
- src/auth/tokens.ts

TASK: For each file, extract:
1. The primary function/class exported
2. The external dependencies used
3. The data flow (what goes in, what comes out)

OUTPUT FORMAT:
| File | Primary Export | Dependencies | Input → Output |
|------|---------------|--------------|----------------|
| ...  | ...           | ...          | ...            |

NEXT: After completing this table, proceed to Step 3.
```

### 1.2 Step-by-Step Instruction Blocks with "NEXT:" Directives

Embed explicit control flow within the prompt. The agent reads a block, executes it, then follows the `NEXT:` directive.

**Pattern:** Each instruction block is self-contained with a clear entry condition, task, output requirement, and exit directive.

```
═══════════════════════════════════════
PHASE 2: DEEP ANALYSIS
═══════════════════════════════════════

ENTRY CONDITION: Phase 1 file inventory is complete with ≥1 file listed.

DO:
1. Read each file identified in Phase 1.
2. For each file, extract:
   - Purpose (one sentence)
   - Key functions/methods (name + signature)
   - Dependencies (imports)
   - Data models (types, interfaces, schemas)
3. Record findings in the ANALYSIS_NOTES section below.

OUTPUT REQUIREMENT: Every file from Phase 1 must have a corresponding entry.

NEXT: When all files are analyzed, proceed to PHASE 3: SYNTHESIS.
IF BLOCKED: If a file cannot be read, note it as "[UNREADABLE: reason]" and continue.
```

**Why this works:** The agent never has to decide "what should I do next?" — the directive is explicit. This eliminates drift and ensures forward progress.

### 1.3 State Tracking

The agent must maintain an explicit representation of what has been done and what remains. Without this, the agent loses track after context compaction.

**Pattern:** A mutable state block that the agent updates after each step.

```
╔══════════════════════════════════════╗
║          EXECUTION STATE             ║
╠══════════════════════════════════════╣
║ Phase 1: File Discovery    [✅ DONE] ║
║ Phase 2: Deep Analysis     [🔄 IN PROGRESS - 3/7 files] ║
║ Phase 3: Synthesis         [⏳ PENDING] ║
║ Phase 4: Draft PRD         [⏳ PENDING] ║
║ Phase 5: Self-Review       [⏳ PENDING] ║
║ Phase 6: Final Output      [⏳ PENDING] ║
╠══════════════════════════════════════╣
║ Files analyzed: auth.ts, login.ts, middleware.ts ║
║ Files remaining: signup.ts, tokens.ts, types.ts, utils.ts ║
║ Issues found: 0                      ║
║ Iteration: 1 of 3                   ║
╚══════════════════════════════════════╝
```

**Critical rule:** After every action, the agent must update this state block. If context is compacted, the state block serves as the single source of truth for resumption.

### 1.4 Structured Output Enforcement

Force the agent to fill a predefined template rather than generating free-form text. Templates eliminate the "blank page" problem and ensure completeness.

**Pattern:** Provide a skeleton with placeholder markers the agent must replace.

```
## Feature: {{FEATURE_NAME}}

### Problem Statement
{{Describe the user problem in 2-3 sentences. Must reference specific user pain points.}}

### Proposed Solution
{{Describe the solution in 3-5 sentences. Must reference specific technical components.}}

### Acceptance Criteria
- [ ] {{Criterion 1: Must be testable and specific}}
- [ ] {{Criterion 2: Must be testable and specific}}
- [ ] {{Criterion 3: Must be testable and specific}}
(Minimum 3 criteria required)

### Technical Dependencies
- {{Dependency 1: package/service name + version if applicable}}
(List ALL dependencies. Write "None" if truly none.)

### Out of Scope
- {{Item 1: Explicitly state what this feature does NOT include}}
(Minimum 1 item required)
```

**Enforcement rule:** After filling the template, the agent must verify that no `{{placeholder}}` markers remain. Any remaining placeholder is a completeness failure.

### 1.5 Phase Gates

Prevent the agent from advancing until the current phase meets explicit quality criteria.

**Pattern:** A gate check between phases that must pass before proceeding.

```
═══════════════════════════════════════
GATE CHECK: Phase 2 → Phase 3
═══════════════════════════════════════

Before proceeding to Phase 3, verify ALL of the following:

□ Every file from the Phase 1 inventory has an analysis entry
□ No analysis entry contains "TODO" or "TBD"
□ At least 3 data models have been identified
□ All identified dependencies are real (not hallucinated)
□ The analysis notes contain specific function names, not generic descriptions

RESULT: [ ] ALL CHECKS PASS → Proceed to Phase 3
         [ ] SOME CHECKS FAIL → List failures and re-execute Phase 2 for failing items

FAILURES (if any):
- ...
```

**Why gates matter:** Without them, the agent will happily produce a PRD based on incomplete research. Gates force thoroughness.

---

## 2. Self-Correction / Reflection Loops

Self-correction is the mechanism by which an agent detects and fixes errors in its own output. This is the single most important capability for producing quality output.

### 2.1 Reflection Prompts

After producing output, instruct the agent to explicitly review it.

**Pattern:** A structured reflection prompt that forces specific evaluation axes.

```
═══════════════════════════════════════
REFLECTION: Review Your Draft
═══════════════════════════════════════

You just produced a draft of Section 3: Technical Architecture.
Now review it by answering EACH question below:

1. COMPLETENESS: Does this section address every component mentioned
   in the research notes? List any missing components.

2. ACCURACY: Does every technical claim trace back to something you
   observed in the codebase? Flag any claims you're uncertain about.

3. SPECIFICITY: Are there any vague phrases like "various components",
   "should work", "might need", "etc."? Replace each with concrete details.

4. CONSISTENCY: Does this section contradict anything in Sections 1 or 2?
   If so, which section is correct?

5. ACTIONABILITY: Could a developer implement this section without asking
   clarifying questions? If not, what's missing?

After answering all 5 questions, produce REVISION ACTIONS:
- [FIX] items that need correction
- [ADD] items that are missing
- [CUT] items that don't belong

Then apply all revision actions and produce the updated section.
```

**Key insight:** The reflection must be structured with specific evaluation axes. "Is this good?" is useless. "Does every technical claim trace to codebase evidence?" is actionable.

### 2.2 Verification Checklists

Provide a concrete checklist the agent runs against its output. Each item is binary: pass or fail.

**Example checklist for a PRD:**

```
PRD VERIFICATION CHECKLIST
═══════════════════════════

Structure Checks:
  □ Title is present and descriptive
  □ Problem statement references real user needs
  □ Every section in the template is filled (no placeholders remain)
  □ Acceptance criteria are testable (no "should be good")
  □ At least 5 acceptance criteria are defined
  □ Technical dependencies list real packages/services
  □ Out-of-scope section has at least 2 items

Content Checks:
  □ No use of "etc.", "and so on", "various", "some"
  □ All referenced files/functions exist in the codebase
  □ No contradictions between sections
  □ User stories follow "As a [role], I want [goal], so that [benefit]"
  □ Every feature maps to at least one acceptance criterion

Evidence Checks:
  □ Every technical claim cites a specific file or code reference
  □ No requirements are invented without codebase evidence
  □ Current behavior is described based on actual code, not assumptions

Score: ___/15 checks passing
Required: 13/15 minimum to proceed
```

### 2.3 Convergence Protocols

Design loops that iterate toward a stable, correct output — not endlessly.

**Pattern: The Shrinking Issues Loop**

```
CONVERGENCE PROTOCOL
═══════════════════════

MAX_ITERATIONS = 3
issues_remaining = []

FOR iteration IN 1..MAX_ITERATIONS:
  1. Run VERIFICATION CHECKLIST against current output
  2. Collect all failing checks into issues_remaining
  3. IF len(issues_remaining) == 0: BREAK → Output is final
  4. IF iteration > 1 AND len(issues_remaining) >= previous_count:
       BREAK → Not converging, output current best with warnings
  5. For each issue in issues_remaining:
       - Identify the root cause
       - Apply a specific fix
       - Verify the fix resolved the issue
  6. previous_count = len(issues_remaining)

END FOR

IF issues_remaining > 0:
  Append "KNOWN ISSUES" section listing unresolved items
```

**Critical rule:** Track the issue count between iterations. If it's not decreasing, stop — the agent is oscillating, not converging.

### 2.4 "Fresh Eyes" Auditing

Instruct the agent to re-read its output as if encountering it for the first time, stripped of the context of how it was produced.

**Pattern:**

```
FRESH EYES AUDIT
════════════════

Forget everything about how you produced this document.
Read it as if you are a new team member seeing it for the first time.

For each section, answer:
1. Do I understand what this is saying without referring to the codebase?
2. Are there any acronyms or terms used without definition?
3. Is there enough context for someone unfamiliar with the project?
4. Are there any logical jumps where an intermediate step is missing?
5. If I had to implement this, what questions would I ask?

Record your questions. Each question represents a gap in the document.
Then go back and fill every gap.
```

**Why this works:** The agent's "author bias" means it fills in mental gaps when re-reading its own work. The "fresh eyes" framing partially mitigates this by forcing the agent to evaluate from a different perspective.

### 2.5 Structured Self-Critique Templates

Provide a formal template for self-critique that separates identification of issues from resolution.

```
SELF-CRITIQUE TEMPLATE
══════════════════════

SECTION UNDER REVIEW: [Section Name]

STRENGTHS (what's working well):
1. ...
2. ...

WEAKNESSES (what needs improvement):
1. Issue: [description]
   Severity: [Critical / Major / Minor]
   Evidence: [why this is a problem]
   Fix: [specific action to resolve]
2. ...

MISSING ELEMENTS (what's absent):
1. [element] — needed because [reason]
2. ...

VERDICT: [PASS / REVISE / REWRITE]

IF REVISE: Apply fixes to weaknesses, then re-run this template.
IF REWRITE: The section is fundamentally flawed. Start over with [specific guidance].
IF PASS: Proceed to next section.
```

### 2.6 Diff-Based Correction

Compare the agent's output against the original requirements to ensure alignment.

**Pattern:**

```
REQUIREMENTS ALIGNMENT CHECK
═════════════════════════════

Original Requirements:
  R1: Users must be able to log in with email/password
  R2: Sessions must expire after 24 hours
  R3: Password reset via email link
  R4: Rate limiting on login attempts (5 per minute)

For each requirement, find where it appears in the PRD:

  R1 → Section 3.1, Acceptance Criteria #1, #2   ✅ COVERED
  R2 → Section 3.2, Acceptance Criteria #5        ✅ COVERED
  R3 → ???                                         ❌ MISSING
  R4 → Section 3.3, but no specific rate limit     ⚠️ INCOMPLETE

ACTIONS:
  - R3: Add password reset feature to Section 3.4
  - R4: Add specific rate limit value (5 req/min) to Section 3.3
```

---

## 3. Research Agent Patterns

Research agents must systematically explore a codebase to gather accurate, comprehensive information before generating documents.

### 3.1 Breadth-First Exploration

Start wide, then go deep. This prevents the agent from getting lost in details before understanding the overall structure.

**Pattern: Three-Pass Exploration**

```
RESEARCH PROTOCOL: THREE-PASS EXPLORATION
══════════════════════════════════════════

PASS 1: STRUCTURAL SURVEY (breadth-first)
  Goal: Understand the project layout
  Actions:
    1. List top-level directory structure
    2. Identify the technology stack (package.json, requirements.txt, go.mod, etc.)
    3. Read README and any documentation files
    4. Identify entry points (main files, index files, app files)
  Output: PROJECT_OVERVIEW with tech stack, architecture style, and key directories

PASS 2: COMPONENT MAPPING (targeted breadth)
  Goal: Understand what each major component does
  Actions:
    1. For each key directory from Pass 1:
       a. List files and identify their apparent purpose from names
       b. Read the primary/index file to understand the component's role
       c. Note exports, interfaces, and public APIs
    2. Map dependencies between components
  Output: COMPONENT_MAP with purpose, interfaces, and dependency graph

PASS 3: DEEP ANALYSIS (targeted depth)
  Goal: Extract detailed information for the specific task
  Actions:
    1. Based on the task requirements, identify which components need deep analysis
    2. For each target component:
       a. Read every file
       b. Extract data models, business logic, error handling
       c. Identify patterns and anti-patterns
       d. Note technical debt and TODOs
  Output: DETAILED_FINDINGS per component
```

### 3.2 Targeted Deep Dives

When the agent needs to understand a specific flow (e.g., "how does authentication work?"), use a trace-based approach.

**Pattern: Flow Tracing**

```
TRACE PROTOCOL: Follow the Request
═══════════════════════════════════

TARGET FLOW: User Login

1. ENTRY POINT: Find where login requests enter the system
   → Search for: route definitions containing "login", "auth", "signin"
   → Result: POST /api/auth/login → src/routes/auth.ts:42

2. HANDLER: Read the route handler
   → What validation occurs?
   → What service/function is called?
   → Result: Calls AuthService.login(email, password)

3. SERVICE LAYER: Follow the service call
   → Where is AuthService defined?
   → What does .login() do step by step?
   → Result: src/services/auth.service.ts — validates credentials,
     generates JWT, stores session

4. DATA LAYER: Follow database interactions
   → What queries are executed?
   → What models/tables are involved?
   → Result: User table lookup, Session table insert

5. RESPONSE: What does the client receive?
   → Success response shape
   → Error response shapes
   → Result: { token: string, user: UserProfile }

OUTPUT: Complete flow diagram from HTTP request to HTTP response,
        with every file and function involved.
```

### 3.3 Information Extraction Templates

Define what to extract from each file type so the agent doesn't miss important details.

```
EXTRACTION TEMPLATES BY FILE TYPE
═════════════════════════════════

Route/Controller Files:
  - HTTP method + path
  - Middleware applied (auth, validation, rate limiting)
  - Request body/params schema
  - Response schema
  - Error codes returned

Service/Business Logic Files:
  - Public methods (name, params, return type)
  - Business rules enforced
  - External service calls
  - Error handling strategy
  - Side effects (emails sent, events emitted, logs written)

Data Model/Schema Files:
  - Entity name and fields (name, type, constraints)
  - Relationships (foreign keys, references)
  - Indexes
  - Validation rules
  - Default values

Configuration Files:
  - Environment variables used
  - Feature flags
  - Service URLs / connection strings (note: never extract actual secrets)
  - Configurable limits/thresholds

Test Files:
  - What scenarios are tested
  - What edge cases are covered
  - What's NOT tested (gaps)
  - Test data patterns
```

### 3.4 Synthesizing Findings into Structured Notes

Raw findings must be synthesized into usable notes before document generation.

**Pattern: The Research Synthesis Template**

```
RESEARCH SYNTHESIS
══════════════════

COMPONENT: [Name]
FILES EXAMINED: [list]
CONFIDENCE: [High / Medium / Low]

WHAT IT DOES:
  [2-3 sentence summary of the component's purpose]

HOW IT WORKS:
  1. [Step 1 of the main flow]
  2. [Step 2]
  3. [Step N]

KEY INTERFACES:
  - Input: [what it receives, from where]
  - Output: [what it produces, to where]

DATA MODELS:
  - [Model 1]: [fields and purpose]
  - [Model 2]: [fields and purpose]

DEPENDENCIES:
  - [Internal: other components it calls]
  - [External: third-party packages/services]

CURRENT ISSUES / TECHNICAL DEBT:
  - [Issue 1 with evidence]
  - [Issue 2 with evidence]

OPEN QUESTIONS:
  - [Things the agent couldn't determine from the code alone]
```

### 3.5 Handling Large Codebases

When a codebase is too large to read entirely, use prioritization and sampling strategies.

**Strategies:**

1. **Relevance filtering:** Before reading any file, assess its likely relevance to the task based on its name and location. Only deep-dive into relevant files.

2. **Entry-point-first:** Start from known entry points (main files, route definitions, API handlers) and follow call chains. Stop when you've traced 3 levels deep.

3. **Sampling:** For large directories with many similar files (e.g., 50 API routes), read 3-5 representative samples and note the pattern. Only read others if they appear to deviate.

4. **Size-based prioritization:** Larger files often contain more important logic. Prioritize files > 100 lines over small utility files.

5. **Recency-based prioritization:** Recently modified files may be more relevant to current work. Check git history if available.

```
LARGE CODEBASE PROTOCOL
════════════════════════

IF total files > 100:
  1. Read directory structure only (no file contents)
  2. Identify the 10 most relevant directories for the task
  3. Within those directories, identify the 20 most relevant files
  4. Deep-dive into those 20 files
  5. For remaining files, use filename/path to infer purpose
  6. Note: "Files not examined: [list]. Assumed to be [pattern]."

IF a single directory has > 20 files of the same type:
  1. Read 5 samples (first, last, largest, smallest, most recently modified)
  2. Identify the common pattern
  3. Note: "[N] files follow [pattern]. Samples examined: [list]."

ALWAYS note what you DID NOT read, so the human knows the boundaries
of your knowledge.
```

---

## 4. Output Quality Enforcement

Quality enforcement ensures the agent's output meets minimum standards before it's considered complete.

### 4.1 Schema Validation

Define a strict schema for the output and validate against it.

**Pattern: JSON Schema for PRD Sections**

```json
{
  "prd_section": {
    "title": { "type": "string", "minLength": 5 },
    "description": { "type": "string", "minLength": 50 },
    "user_stories": {
      "type": "array",
      "minItems": 2,
      "items": {
        "type": "object",
        "required": ["role", "goal", "benefit"],
        "properties": {
          "role": { "type": "string", "minLength": 3 },
          "goal": { "type": "string", "minLength": 10 },
          "benefit": { "type": "string", "minLength": 10 }
        }
      }
    },
    "acceptance_criteria": {
      "type": "array",
      "minItems": 3,
      "items": { "type": "string", "minLength": 20 }
    },
    "technical_notes": { "type": "string" },
    "out_of_scope": {
      "type": "array",
      "minItems": 1
    }
  }
}
```

**Validation prompt:**

```
SCHEMA VALIDATION
═════════════════

Check the output against these rules:
□ Title exists and is ≥5 characters
□ Description exists and is ≥50 characters
□ At least 2 user stories, each with role + goal + benefit
□ At least 3 acceptance criteria, each ≥20 characters
□ Technical notes section exists (may be empty if justified)
□ At least 1 out-of-scope item

For each failing rule, note the violation and fix it immediately.
```

### 4.2 Completeness Scoring

Quantify how complete the output is. This gives the agent (and the human) a concrete measure.

```
COMPLETENESS SCORECARD
══════════════════════

Section                     | Status      | Score
----------------------------|-------------|------
1. Overview                 | Complete    | 10/10
2. Problem Statement        | Complete    | 10/10
3. User Stories              | 3 of 5 done | 6/10
4. Technical Architecture   | Missing     |  0/10
5. Acceptance Criteria      | Complete    | 10/10
6. Dependencies             | Partial     |  5/10
7. Timeline                 | Complete    | 10/10
8. Out of Scope             | Complete    | 10/10
9. Open Questions           | Not started |  0/10
10. Appendix                | N/A         | 10/10

TOTAL: 71/100
THRESHOLD: 85/100 required to finalize
STATUS: ❌ NOT READY — Address sections 3, 4, 6, 9
```

### 4.3 Ambiguity Detection

Scan for weasel words and vague language that undermine document quality.

**Pattern: Banned Phrase List**

```
AMBIGUITY SCAN
══════════════

Scan the output for these patterns and replace each with specific language:

BANNED PHRASES → REQUIRED REPLACEMENT
  "various"          → List the specific items
  "etc."             → Complete the list or write "including X, Y, and Z"
  "and so on"        → Complete the list explicitly
  "should"           → "MUST" or "SHOULD" (per RFC 2119) with justification
  "might"            → "WILL" or "MAY" with conditions stated
  "could"            → State whether it WILL or WON'T, and under what conditions
  "some"             → State the specific quantity or list the items
  "many"             → State the approximate number
  "soon"             → State the specific date or milestone
  "simple"           → Remove or describe the actual complexity
  "straightforward"  → Remove or describe the actual steps
  "obviously"        → Remove (if it's obvious, it doesn't need saying)
  "probably"         → State the conditions and confidence level
  "as needed"        → Define the specific trigger conditions
  "if applicable"    → State when it applies and when it doesn't

FOUND INSTANCES:
  Line 42: "various authentication methods" → Replace with "OAuth2, email/password, and SSO"
  Line 87: "should handle errors" → Replace with "MUST return HTTP 4xx with error body"
```

### 4.4 Cross-Reference Validation

Verify that items referenced in the document actually exist.

```
CROSS-REFERENCE VALIDATION
═══════════════════════════

For each technical reference in the document:

1. File references:
   □ "src/auth/login.ts" — Does this file exist? → YES/NO
   □ "src/models/User.ts" — Does this file exist? → YES/NO

2. Function references:
   □ "AuthService.validateToken()" — Does this function exist? → YES/NO
   □ "hashPassword()" — Does this function exist? → YES/NO

3. Package references:
   □ "jsonwebtoken" — Is this in package.json? → YES/NO
   □ "bcrypt" — Is this in package.json? → YES/NO

4. API endpoint references:
   □ "POST /api/auth/login" — Is this route defined? → YES/NO
   □ "GET /api/users/me" — Is this route defined? → YES/NO

INVALID REFERENCES FOUND:
  - "src/auth/validate.ts" does not exist. Actual file: "src/auth/validation.ts"
  - "UserService.getProfile()" does not exist. Actual: "UserService.findById()"

ACTION: Correct all invalid references before finalizing.
```

### 4.5 Minimum Detail Thresholds

Set hard minimums for each section to prevent thin, hand-wavy content.

```
MINIMUM DETAIL THRESHOLDS
══════════════════════════

Section                    | Minimum Requirement
---------------------------|--------------------------------------------
Problem Statement          | ≥3 sentences, ≥1 specific user pain point
User Stories               | ≥3 stories, each with role/goal/benefit
Acceptance Criteria        | ≥5 criteria, each testable (no subjective language)
Technical Architecture     | ≥1 diagram OR ≥5 component descriptions
API Specifications         | Every endpoint: method, path, request, response, errors
Data Models                | Every field: name, type, constraints, description
Dependencies               | Every dependency: name, version, purpose
Security Considerations    | ≥3 specific security measures
Performance Requirements   | ≥2 specific metrics with target values
Out of Scope               | ≥2 explicit exclusions

IF any section falls below its threshold:
  → Do NOT finalize. Return to research phase for that section.
  → Note: "Section [X] below minimum. Need: [specific missing items]."
```

---

## 5. Anti-Patterns to Avoid

These are failure modes that commonly derail self-prompting agents.

### 5.1 Infinite Loops Without Convergence Criteria

**The problem:** The agent enters a review-revise cycle that never terminates because it keeps finding new issues or flip-flopping between alternatives.

**The fix:**
- Always set `MAX_ITERATIONS` (typically 2-3)
- Track issue count per iteration; break if it's not decreasing
- Define "good enough" explicitly: "If ≤2 minor issues remain after iteration 3, finalize with known-issues section"

```
# BAD: No termination condition
while issues_exist:
    review()
    fix()

# GOOD: Bounded with convergence check
for i in range(MAX_ITERATIONS):
    issues = review()
    if len(issues) == 0:
        break
    if i > 0 and len(issues) >= previous_issue_count:
        break  # Not converging
    fix(issues)
    previous_issue_count = len(issues)
```

### 5.2 Over-Reliance on Previous Context

**The problem:** After many steps, the agent's earlier findings may have been compacted or summarized. The agent then works from degraded information, introducing errors.

**The fix:**
- Maintain a persistent state document that survives compaction
- Before critical phases, instruct the agent to re-read source files rather than relying on earlier notes
- Use explicit context refresh instructions:

```
CONTEXT REFRESH (before Phase 4):
══════════════════════════════════

WARNING: Your earlier analysis may have been summarized. Before writing
the PRD draft, RE-READ these critical files to refresh your understanding:
  1. src/auth/middleware.ts — for the exact auth flow
  2. src/models/User.ts — for the exact field names and types

DO NOT rely on your memory of these files. Read them again NOW.
```

### 5.3 Hallucinating Requirements

**The problem:** The agent invents requirements that aren't supported by the codebase or the user's request. It "fills in the blanks" with plausible-sounding but fictional features.

**The fix:**
- Require evidence citations for every claim
- Distinguish between "observed" (in the code), "inferred" (logical deduction), and "assumed" (not in evidence)
- Flag assumptions explicitly:

```
EVIDENCE CLASSIFICATION
═══════════════════════

Every statement in the PRD must be tagged:

[OBSERVED] — Directly seen in the codebase
  Example: "The User model has an 'email' field (src/models/User.ts:15)"

[INFERRED] — Logically deduced from observations
  Example: "Since login requires email+password and there's no OAuth
  route, the system currently only supports credential-based auth"

[ASSUMED] — Not in evidence; the agent's best guess
  Example: "Assuming the team wants to support SSO in the future"

RULE: [ASSUMED] items MUST be flagged with "⚠️ ASSUMPTION — Verify with team"
      and placed in the "Open Questions" section, not in requirements.
```

### 5.4 Confirmation Bias in Self-Review

**The problem:** The agent produced the output, so it's predisposed to find it acceptable. Self-review tends to be lenient.

**The fix:**
- Use adversarial review prompts ("Find 3 things wrong with this")
- Force the agent to argue against its own output
- Use specific, checkable criteria rather than subjective quality assessments

```
ADVERSARIAL REVIEW
══════════════════

You MUST find at least 3 issues with the document below. They may be:
  - Missing information
  - Inaccurate claims
  - Vague language
  - Logical inconsistencies
  - Unjustified assumptions

DO NOT say "the document looks good." That is not an acceptable output
from this review step. If you truly cannot find 3 issues, find 2 issues
and 1 improvement suggestion.
```

### 5.5 Scope Creep During Research

**The problem:** The agent follows interesting dependency chains deeper and deeper, exploring tangentially related code, burning context window and time on irrelevant details.

**The fix:**
- Define the research scope explicitly before starting
- Set a file/directory budget
- Use a relevance filter at each step:

```
SCOPE BOUNDARY
══════════════

RESEARCH TARGET: Authentication system
IN SCOPE: Files in src/auth/*, authentication middleware, User model, Session model
OUT OF SCOPE: Payment processing, email templates, admin dashboard, test fixtures

BEFORE reading any file, ask: "Does this file directly implement or support
authentication?" If NO, skip it and note: "Skipped [file] — out of scope."

FILE BUDGET: Read at most 25 files in depth. Currently at: 0/25.
```

### 5.6 Not Re-Reading Source Material After Context Compaction

**The problem:** After a long session, the agent's understanding of earlier files degrades due to context window limitations. It then generates output based on stale or summarized information.

**The fix:**
- At the start of each major phase, re-read the most critical files
- Keep a "critical files" list that must be refreshed before generation
- Never generate final output without a fresh read of source material

```
PRE-GENERATION REFRESH
══════════════════════

Before writing the final PRD, re-read these files in order:
1. Requirements document (if one exists)
2. The 3 most critical source files identified during research
3. Any configuration files that define system behavior

This is not optional. Stale context produces inaccurate output.
```

---

## 6. Prompt Engineering for Agent Chains

These are the specific techniques for writing prompts that drive multi-step agent workflows.

### 6.1 Imperative Voice

Use direct commands, not suggestions. The agent should never have to interpret whether an instruction is optional.

```
# BAD: Suggestive
"You might want to check if the file exists before reading it."
"It would be helpful to list the dependencies."
"Consider examining the test files for additional context."

# GOOD: Imperative
"CHECK if the file exists before reading it. If it does not exist, record '[MISSING]' and continue."
"LIST all dependencies from package.json. Include name, version, and purpose."
"READ test files in src/__tests__/auth/ to identify tested scenarios."
```

### 6.2 Explicit Stop Conditions

Tell the agent exactly when to stop. Without this, agents either stop too early or continue indefinitely.

```
STOP CONDITIONS:
  1. STOP RESEARCHING when you have analyzed all files in the target directories
     OR when you have hit the 25-file budget, whichever comes first.
  2. STOP ITERATING when the verification checklist scores ≥85%
     OR when you have completed 3 iteration cycles, whichever comes first.
  3. STOP AND ASK A HUMAN when you encounter a requirement that contradicts
     another requirement and you cannot determine which is authoritative.
```

### 6.3 Numbered Step Sequences

Number every step. This makes it easy for the agent to track progress and for humans to audit the agent's work.

```
EXECUTE THESE STEPS IN ORDER:

1. Read the project's package.json and extract:
   a. Project name and version
   b. All dependencies (production and dev)
   c. All scripts defined

2. Read the project's tsconfig.json (if it exists) and extract:
   a. Target JavaScript version
   b. Module system
   c. Path aliases

3. Read the project's README.md and extract:
   a. Project description
   b. Setup instructions
   c. Architecture overview (if present)

4. COMPILE your findings into the PROJECT_OVERVIEW template.

5. VERIFY the PROJECT_OVERVIEW has no empty fields.
   If any field is empty, go back to the relevant file and try again.
   If the information truly doesn't exist, write "[NOT FOUND IN PROJECT]".
```

### 6.4 Template Placeholders with Fill Instructions

Use clear placeholder syntax with inline instructions for what should replace them.

```
## {{FEATURE_NAME — use the exact name from the requirements doc}}

### Problem
{{2-3 sentences describing the user problem. Start with "Users currently..."
and describe the pain point. Do not describe the solution here.}}

### Solution
{{3-5 sentences describing what will be built. Start with "This feature will..."
Reference specific components from the codebase analysis.}}

### Technical Approach
{{Describe the implementation strategy. Include:
- Which existing files will be modified (with paths)
- What new files will be created (with proposed paths)
- Which libraries/packages will be used
- Data model changes required}}
```

### 6.5 Verification Gates Between Phases

Insert explicit checkpoints where the agent must pause, verify, and report before continuing.

```
════════════════════════════════════════════════
CHECKPOINT: End of Research Phase
════════════════════════════════════════════════

Before proceeding to the Writing Phase, STOP and complete this checklist:

1. How many files did you examine? ___
2. How many components did you identify? ___
3. What is the primary technology stack? ___
4. List the 3 most critical files for this task:
   a. ___
   b. ___
   c. ___
5. What information are you MISSING that you wish you had? ___
6. Confidence level in your research (High/Medium/Low): ___

IF confidence is Low:
  → Go back and read more files. You are not ready to write.
IF confidence is Medium:
  → Note gaps in an "Assumptions & Open Questions" section.
IF confidence is High:
  → Proceed to Writing Phase.
```

### 6.6 Context Refresh Instructions

Explicitly instruct the agent to re-read specific information before critical steps.

```
═══════════════════════════════════════
CONTEXT REFRESH — Required Before Phase 4
═══════════════════════════════════════

Your context may have degraded. Before writing the PRD draft:

1. RE-READ the execution state block at the top of this document
2. RE-READ your research synthesis notes from Phase 2
3. RE-READ the PRD template you must fill
4. RE-READ the verification checklist you will be graded against

DO NOT proceed until you have refreshed on all 4 items.
After refreshing, state: "Context refreshed. Proceeding to Phase 4."
```

### 6.7 Escape Hatches

Define conditions under which the agent should stop and request human input rather than guessing.

```
ESCAPE HATCHES — Stop and Ask a Human When:
════════════════════════════════════════════

1. CONFLICTING REQUIREMENTS: Two requirements contradict each other
   and the code doesn't clarify which is authoritative.
   → Stop. Present both requirements and ask which takes priority.

2. MISSING CRITICAL INFORMATION: A core piece of information needed
   for the PRD cannot be found in the codebase or documentation.
   → Stop. List what's missing and where you looked.

3. AMBIGUOUS SCOPE: The task could be interpreted in multiple
   materially different ways.
   → Stop. Present the interpretations and ask which is intended.

4. SECURITY CONCERNS: You identify a security issue that the PRD
   might inadvertently perpetuate or worsen.
   → Stop. Flag the concern before proceeding.

5. EXCEEDED BUDGET: You've hit the file read limit or iteration cap
   without sufficient information.
   → Stop. Report what you have and what you're missing.

FORMAT for escape:
  ⛔ HUMAN INPUT NEEDED
  Reason: [1-5 from above]
  Context: [what you know]
  Question: [specific question for the human]
  Options: [if applicable, present choices]
```

---

## 7. Convergence Protocol Design

Convergence protocols ensure that iterative loops move toward a stable, high-quality output rather than oscillating or degrading.

### 7.1 Define "Done" Precisely

Ambiguous completion criteria cause agents to either stop prematurely or loop forever.

```
DEFINITION OF DONE
══════════════════

The PRD is DONE when ALL of the following are true:

  ✅ Every section in the template is filled (no placeholders)
  ✅ Verification checklist scores ≥ 85% (at least 13/15 checks pass)
  ✅ Ambiguity scan finds 0 banned phrases
  ✅ All cross-references validated (files/functions/endpoints exist)
  ✅ At least 3 acceptance criteria per feature
  ✅ All [ASSUMED] items moved to Open Questions section
  ✅ Fresh-eyes audit produces 0 unanswered questions of severity "Critical"

The PRD is NOT done if:
  ❌ Any section contains placeholder text
  ❌ Verification score is < 85%
  ❌ Any cross-reference is invalid
  ❌ Any [ASSUMED] item is presented as a requirement
```

### 7.2 Cap Iterations

Always set a maximum number of refinement cycles. Two to three is typically sufficient; beyond that, returns diminish rapidly.

```
ITERATION POLICY
════════════════

MAX_ITERATIONS = 3

Iteration 1: Generate draft → Run full verification → Fix all issues
Iteration 2: Run full verification on revised draft → Fix remaining issues
Iteration 3 (final): Run full verification → Fix critical issues only

After Iteration 3:
  IF score ≥ 85%: Finalize
  IF score < 85%: Finalize with KNOWN_ISSUES section appended
  NEVER do Iteration 4. Diminishing returns make it counterproductive.
```

### 7.3 Track What Changed Between Iterations

Maintain a changelog between iterations to ensure progress and prevent regression.

```
ITERATION CHANGELOG
═══════════════════

Iteration 1 → 2:
  FIXED:
    - Added missing "Password Reset" user story (was absent)
    - Replaced "various endpoints" with specific endpoint list
    - Corrected file reference: validate.ts → validation.ts
  SCORE: 9/15 → 12/15 (+3)

Iteration 2 → 3:
  FIXED:
    - Added rate limiting acceptance criteria (was below threshold)
    - Moved 2 [ASSUMED] items to Open Questions
    - Added error response schemas to API section
  SCORE: 12/15 → 14/15 (+2)

TREND: Monotonically improving ✅ (9 → 12 → 14)
```

### 7.4 Require Monotonic Improvement

Each iteration must reduce the number of issues. If it doesn't, the agent is oscillating and should stop.

```
MONOTONIC IMPROVEMENT CHECK
════════════════════════════

After each iteration, compare:
  current_issues = count of failing verification checks
  previous_issues = count from the previous iteration

IF current_issues < previous_issues:
  ✅ Improving. Continue to next iteration (if under MAX_ITERATIONS).

IF current_issues == previous_issues:
  ⚠️ Stalled. The agent is not making progress.
  ACTION: Try a different approach to the remaining issues.
  If still stalled after retry: STOP and finalize with known issues.

IF current_issues > previous_issues:
  ❌ Regressing. The agent is making things worse.
  ACTION: REVERT to the previous iteration's output.
  Finalize with the previous version + known issues from that version.
```

### 7.5 Final Handoff Protocol

When the agent reaches its maximum iterations or achieves convergence, it must produce a clean handoff.

```
FINAL HANDOFF PROTOCOL
══════════════════════

When finalizing, produce this summary block at the top of the output:

╔══════════════════════════════════════════════╗
║              GENERATION SUMMARY              ║
╠══════════════════════════════════════════════╣
║ Status: [COMPLETE / COMPLETE WITH CAVEATS]   ║
║ Iterations: [N] of [MAX]                     ║
║ Verification Score: [X]/[Y] ([Z]%)           ║
║ Files Examined: [N]                          ║
║ Confidence: [High / Medium / Low]            ║
╠══════════════════════════════════════════════╣
║ KNOWN ISSUES (if any):                       ║
║ 1. [Issue description + severity]            ║
║ 2. [Issue description + severity]            ║
╠══════════════════════════════════════════════╣
║ ASSUMPTIONS MADE (requiring verification):   ║
║ 1. [Assumption + what would change if wrong] ║
║ 2. [Assumption + what would change if wrong] ║
╠══════════════════════════════════════════════╣
║ RECOMMENDED NEXT STEPS:                      ║
║ 1. [Human action needed]                     ║
║ 2. [Human action needed]                     ║
╚══════════════════════════════════════════════╝
```

---

## Appendix A: Complete Self-Prompting PRD Agent — Reference Architecture

Below is a complete, minimal prompt structure for a self-prompting PRD generation agent. This ties together all patterns from this report.

```
╔══════════════════════════════════════════════════════════╗
║         SELF-PROMPTING PRD GENERATION AGENT              ║
║         Version 1.0                                      ║
╚══════════════════════════════════════════════════════════╝

MISSION: Generate a complete PRD for [FEATURE] by researching the
codebase at [REPO_PATH], analyzing the current implementation,
and producing a structured document.

MAX_ITERATIONS: 3
FILE_BUDGET: 25 files
TARGET_SCORE: 85%

═══ PHASE 1: RESEARCH (Breadth-First) ═══

DO:
1. List the top-level directory structure
2. Identify the tech stack from config files
3. Read README and existing documentation
4. Identify entry points for [FEATURE]

OUTPUT: PROJECT_OVERVIEW block
GATE: PROJECT_OVERVIEW has ≥3 filled fields → Proceed to Phase 2
      Otherwise → Expand research scope

═══ PHASE 2: DEEP ANALYSIS ═══

DO:
1. Trace the primary flow for [FEATURE] (entry point → data layer)
2. For each file in the flow, extract per the extraction template
3. Map dependencies between components
4. Identify gaps in current implementation

OUTPUT: RESEARCH_SYNTHESIS block for each component
GATE: ≥3 components analyzed with High confidence → Proceed to Phase 3
      Otherwise → Analyze more components

═══ PHASE 3: DRAFT PRD ═══

CONTEXT REFRESH: Re-read the PRD template and your research synthesis.

DO:
1. Fill every section of the PRD template
2. Tag claims as [OBSERVED], [INFERRED], or [ASSUMED]
3. Ensure no placeholders remain

OUTPUT: Complete PRD draft
GATE: All sections filled, no placeholders → Proceed to Phase 4
      Otherwise → Fill missing sections

═══ PHASE 4: VERIFICATION LOOP ═══

FOR iteration IN 1..3:
  1. Run VERIFICATION CHECKLIST
  2. Run AMBIGUITY SCAN
  3. Run CROSS-REFERENCE VALIDATION
  4. Calculate score
  5. IF score ≥ 85%: BREAK
  6. IF NOT improving: BREAK
  7. Fix identified issues
  8. Log ITERATION CHANGELOG

═══ PHASE 5: FINALIZE ═══

DO:
1. Run FRESH EYES AUDIT
2. Apply final fixes
3. Generate HANDOFF SUMMARY
4. Output final PRD

═══ EXECUTION STATE (update after every action) ═══

Phase 1: [⏳ PENDING]
Phase 2: [⏳ PENDING]
Phase 3: [⏳ PENDING]
Phase 4: [⏳ PENDING]
Phase 5: [⏳ PENDING]
Files read: 0/25
Current iteration: 0/3
Current score: 0%
```

---

## Appendix B: Quick Reference — Pattern Cheat Sheet

| Pattern | When to Use | Key Element |
|---------|-------------|-------------|
| Chain-of-thought | Breaking down complex tasks | Intermediate artifacts at each step |
| NEXT: directives | Guiding agent through phases | Explicit control flow |
| State tracking | Long-running multi-phase work | Mutable state block |
| Template enforcement | Ensuring complete output | Placeholder markers |
| Phase gates | Preventing premature advancement | Binary pass/fail checks |
| Reflection prompts | Post-generation review | Structured evaluation axes |
| Verification checklists | Quality assurance | Binary checkable items |
| Convergence protocols | Iterative refinement | Issue count tracking + caps |
| Fresh eyes audit | Catching author bias | Perspective shift framing |
| Adversarial review | Overcoming confirmation bias | "Find N things wrong" |
| Breadth-first exploration | Starting codebase research | Structure → Purpose → Detail |
| Flow tracing | Understanding specific features | Entry point → Data layer |
| Ambiguity detection | Improving specificity | Banned phrase list |
| Cross-reference validation | Ensuring accuracy | Verify all refs exist |
| Context refresh | Preventing stale context errors | Re-read before critical phases |
| Escape hatches | Knowing when to stop | Specific stop-and-ask conditions |
| Monotonic improvement | Ensuring convergence | Issue count must decrease |
| Handoff protocol | Clean task completion | Summary block with caveats |

---

*Generated as a reference for building self-prompting PRD generation templates.*
