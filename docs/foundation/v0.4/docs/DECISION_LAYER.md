# Optional fast decision layer — assessment and evaluation gate

**Status:** proposed experiment, disabled by default; not implemented or benchmarked. Verified-source cutoff: 30 September 2026. The founder asked to consider Jev, Ollama System One, and OpenAI's new Decisions API. This is not authorisation to install providers or send data.

## Product fit

A fast typed decision service could help choose a bounded next action. It should not become a second conversational tutor or a replacement for substantive reasoning, evidence or teaching. The experience should be unhurried because the learner controls the pace, not because inference or interface responses are deliberately slow.

Keep four boundaries distinct:

1. Deterministic code enforces ownership, authorisation, schemas, budgets and allowed actions.
2. An optional decision model proposes a choice from candidates already admitted by those rules.
3. A trusted coordinator validates the proposal, handles uncertainty and selects the permitted next step.
4. The teaching/research model supplies explanation or investigates evidence when needed. Desk-owned renderers and the optional MCP Apps adapter present results.

A smaller ordinary generative model emitting JSON is a possible baseline, not automatically equivalent to a purpose-built decision model. Likewise, vendor confidence values are not automatically comparable or calibrated on Desk tasks.

## What was verified

| Candidate | Evidence and limits | Proposed status |
|---|---|---|
| TypeSafe Jev | The provider describes Jev as a System One model returning typed decisions from structured questions, with probabilities/confidence. This confirms the product category, not its accuracy for learning or the exact currently available SDK contract. [S1] | Candidate hosted adapter; verify primary reference, account access, data terms and supported types before implementation. |
| Ollama System One | The official Python README documents a local System One interface, including client methods and requirements. This is a different provider/runtime route, not proof that Jev weights run locally. [S2] | Candidate self-hosted experiment with a compatible model and explicit hardware/license checks. |
| OpenAI Decisions API | A DevDay community announcement mentions this name. A primary request/response reference, endpoint and account eligibility were not verified in this research. The official API changelog was checked but did not establish that contract. [S4, S5] | Named candidate only. Do not invent an endpoint, model ID, SDK method, price or launch promise. Absence of verified docs here does not establish nonexistence. |
| Conventional structured-output model | Official OpenAI documentation describes schema-constrained output support. A valid structure does not establish factual correctness. This can be an evaluation baseline, separately labelled from Decisions. [S3] | Optional comparator, not an implicit substitution or unannounced external fallback. |

TypeSafe's calibration/speed/cost claims are vendor statements, not Desk results. We have not run provider calls, inspected account-specific access, evaluated models or installed SDKs.

### Ollama integration facts to recheck at the spike

The official README specifies `POST /v1/systemone`, Ollama 0.35.0 or later, and a compatible local model such as `nimble`. It exposes `ollama.systemone`, synchronous client and asynchronous client forms. This path returns one JSON response; the documented path does not support streaming or cloud models. Its decision types are `choice`, `noul`, and `score`. The README explicitly distinguishes probability concentration from calibrated correctness. [S2]

Do not infer that all Ollama models support this path, that output token usage is zero, or that putting Ollama on localhost means a configured model is necessarily local. The selected path, model, runtime and data destination must be checked. Version minima are not a security recommendation; use a compatible patched version and inspect its actual API.

## Good first experiments

Choose **one** task first: classify a learner's current message into a small set such as explanation, example, practice, clarification or uncertain. Explicit buttons and unambiguous user commands bypass the classifier rather than paying for a model to rediscover their intent.

A second independent experiment, only after review, could rank already-authorised context snippets or choose between installed, allowed representations. Graph-link suggestions may eventually use a similar candidate mechanism, but confirmation and evidence remain separate. Unknown context must lead to abstention or an appropriate fallback, not fabricated certainty.

Do not initially use this layer to certify sources, score durable mastery, diagnose the learner, detect emotions, approve code, or decide whether private content may be shared. Do not classify every keystroke, cursor movement or frame of an animation. Saved note changes remain context for a relevant later interaction; model speed does not authorise interrupting the learner.

## Proposed data flow

Explicit learner interaction
→ deterministic intent shortcut when sufficient
→ trusted service filters context and candidates by workspace/desk/access/revision
→ optional bounded decision call
→ runtime validation, candidate membership and freshness checks
→ deterministic policy accepts or abstains
→ existing tutor/research path, with budgets and cancellation
→ meaningful outcome recorded independently of latest ephemeral model context.

A result is a recommendation, never a capability grant. No candidate list may include changing note ownership, weakening read permissions, running arbitrary plugins, exporting private material or overriding safety checks.

## Adapter, privacy and failure rules

`contracts/decision-contracts.ts` is Desk's proposed internal vocabulary. It is not a provider wire format. Each adapter maps verified provider types into it, preserving version, rubric, source revisions, usage and the meaning/absence of reported confidence. Never invent a numeric confidence for a provider that does not supply one, and never interpret a typed `score` as calibrated probability by default.

- Default to feature off. P0 uses fixtures and never calls a provider.
- Requests contain the smallest relevant, authorised excerpts. Notes are user data, not instructions. Permission to share with a tutor does not automatically approve a new processor.
- Cancel or discard outdated results after a desk change, sharing revocation, edited source revision or superseding turn. Recheck permissions at dispatch and before applying a result.
- Enforce timeout, request/context limit and maximum calls per interaction in trusted code. No recursive classifier loops.
- Provider outage, schema failure, unknown option or context overflow returns an explicit unavailable/abstain result. Fall back to a previously configured safe path; do not silently send a local-only desk to the cloud.
- Ordinary typed choices do not launch unsolicited tutor turns. No model writes learner notes or grants itself tool access.
- Log operational metadata with content redacted by default. Persist meaningful learning evidence separately; do not log full private request bodies merely to benchmark latency.
- Cost comparison includes the additional routing call, networking, local cold starts and the remaining tutor call—not just the provider's isolated speed claim.

## Evaluation before adoption

Compare deterministic heuristics, a conventional structured-output baseline and one verified candidate on the same versioned cases. Start with synthetic task-specific cases, then use consented examples and reviewed labels. Include ambiguity, mixed intent, corrections, code/quoted instructions, refusal-to-be-quizzed, long inputs and provider failures.

Measure per-class error, abstention/coverage tradeoff, inappropriate intervention, end-to-end latency (p50/p95; local warm/cold), usage/cost and recovery behaviour. Assess calibration only for a defined output meaning and sufficient labelled data. A model's self-reported probability is not an empirical calibration result.

Pass criteria must be set before running the comparison. Adopt only if measured benefits outweigh integration and privacy complexity without regressing learner agency. Retain a feature switch and fallback; no product feature should require a particular decision vendor.

## Relationship to MCP Apps and deployment

MCP Apps concerns presenting/interacting with tools; the decision layer concerns selecting a bounded action. Neither owns note storage or authorisation. The two experiments are independent. A fast model cannot approve an MCP origin or plugin permission.

The default Compose package remains application + PostgreSQL. A local decision runtime may later be an opt-in profile or separately configured service, with documented resource needs and no compulsory GPU download. Hosted Jev or a verified OpenAI adapter remains opt-in through backend configuration, never browser-bundled keys. Self-hosting remains useful with decision inference disabled.

See [the experiment prompt](../prompts/DECISION_LAYER_SPIKE.md), [security](SECURITY_PRIVACY.md), [MCP Apps](MCP_APPS.md) and [source ledger](SOURCES.md).
