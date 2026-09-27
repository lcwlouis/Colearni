# Cards and teaching plugins

## Shared contract, bounded implementations

The application ships reviewed built-in renderers/plugins. They use the same host-facing contract planned for future engines: identity and version, typed input and state, semantic targets, events, source/assumption information, and fallback behaviour. This tests the useful abstraction without implementing a general plugin marketplace.

A teaching plugin is not a Vite build plugin or a browser extension. Keep these names distinct in code and documentation.

## Minimum host-facing descriptor

| Field | Requirement |
|---|---|
| `id`, `version`, `contractVersion` | Stable namespaced identity; exact versions on saved cards. |
| `inputSchemaId`, `stateSchemaId` | Runtime validation of input and saved state. |
| `semanticTargetKinds` | Only advertised, currently resolvable targets can be highlighted. |
| `events` | Allowlisted semantic events with bounded payloads. |
| `runtime` | Prototype: bundled only. Future isolated runtimes need an explicit host adapter. |
| `capabilities` | Declared requirements, not self-granted permissions. |
| `textFallback` | Readable noninteractive explanation of the activity when rendering is unavailable. |
| `assumptions`, `validRanges` | Required when relevant to a model or simulation. |

Registration is explicit in host code. A generated card's engine ID resolves only to an installed allowlisted implementation. Unknown or invalid entries render an unsupported/fallback state. Never dynamically import an arbitrary URL supplied by model output.

Persist learner attempts and notes separately from replaceable generated material. Record which plugin version and input produced a result. Only meaningful interactions are saved; avoid model calls, history entries, or embeddings for each animation frame.

## Two prototype plugins

**Worked example:** reviewed React renderer of a title and ordered steps, with optional explanations and stable step targets. Generated content may later populate the same schema. A reveal control does not require a quiz after every step.

**Scalar function explorer:** developer-authored `y = a*x + b` evaluation and SVG plot with bounded numeric controls, labelled axes, a table/text alternative, reset, and explicit parameter-change events. The fixture uses `x` in `[-5, 5]`, `a` in `[-3, 3]`, and `b` in `[-5, 5]`. Test `a=2,b=1,x=3 → y=7` and `a=0 → y=b`. The model is deterministic and uses no expression evaluation or generated JavaScript. It is not evidence that an orbital-mechanics engine has been validated.

Later plugins can add code diffs, 2D/3D scenes, or richer worksheets without changing ownership and history rules. Do not build a universal physics engine first.

## Built-in trust is not third-party isolation

Bundled code is reviewed as part of the application and may run inside the application process. This does not establish that untrusted code is safe there. Third-party/private-generated execution must use a separately reviewed isolated adapter; a manifest or shared interface does not supply a sandbox.

The shared host contract should allow the adapter boundary without pretending all future capabilities are already known. No private-note access, arbitrary network calls, filesystem access, or app credentials are available through the teaching-plugin interface.

## Future private generation and publication

Private experimental engine → explicit submission → package and provenance inspection → security review → subject-matter and usability/accessibility checks → versioned release → discoverable listing.

Review status belongs to the exact artifact/dependencies, stored by the trusted registry—not an approval field a plugin declares about itself. Keep isolation after review. New releases do not silently change existing sessions. Revocation should block unsafe execution, preserving saved output and an explanation rather than deleting learner work.

Publishing shares a reusable engine, not a desk, private paper, prompts, hidden test data, notes, or learner state. Publication requires deliberate inspection and approval. Agent selection from installed compatible tools is distinct from downloading code or granting permissions. Catalog text is untrusted retrieval data. [R9]

## Deferred security gate

Before any generated/third-party engine runs, specify separate-origin or server runtime isolation, denied-by-default network/secrets, enforceable CPU/memory/time/output limits, message validation, revocation, and reproducibility. Choose and test the actual mechanism before advertising safety. Automated checks do not certify scientific correctness; a safe render can still teach a false model.
