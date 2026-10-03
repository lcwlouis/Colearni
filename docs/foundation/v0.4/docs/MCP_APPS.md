# MCP Apps assessment and Desk integration proposal

**Status: proposed adapter and technical spike, not implemented or approved as the universal runtime.**
**Sources inspected: 29 September 2026.** The overview links the `2026-01-26` specification path. Rolling SDK docs may evolve; pin and test a concrete SDK/protocol combination during the spike instead of claiming that path is the latest possible implementation.

## Decision in one sentence

Use MCP Apps as a candidate standard connection/rendering boundary for interactive teaching tools, while Desk owns notes, tasks, learner evidence, permissions, visual framing, storage and history.

## What the standard provides

MCP Apps associates an MCP tool with an HTML UI resource, commonly through `_meta.ui.resourceUri` and a `ui://` URI. An Apps-capable host renders the interface in an isolated frame and mediates bidirectional messages. This can support forms, plots and 3D viewers; it does not require changing Desk's React/Vite frontend stack. [M1]

The SDK provides `AppBridge` for host-side communication. Its API includes sandbox/resource lifecycle handling and message callbacks; using a bridge does not eliminate the need to construct a correctly isolated host, validate requests and implement permissions. [M4]

Host context can convey theme, style information, dimensions and display-mode information. That helps an app match its surroundings, but does not force it to obey Desk's design rules. [M6]

`ui/update-model-context` can publish a latest context snapshot without asking for a follow-up response. The latest update from a view replaces its preceding update and can be held until the next user interaction. This is a useful fit for the non-helicopter-tutor decision. [M5]

The protocol defines app/model tool visibility and restrictive resource policies; these supplement rather than replace Desk's own grants. Apps may only use tools permitted by the negotiated protocol/connection and host policy. [M3]

## What MCP Apps is not

It is not a database, a Markdown document format, a worksheet schema, a concept graph, a learning assessment system, a safe public marketplace, a domain-correctness certificate, or a guarantee of offline operation. It does not supply Desk's cross-session restore/undo semantics.

Unlike native schema-driven cards, an MCP App contributes an HTML/JavaScript interface. It must go through the separate executable-view boundary, not through an allow-HTML setting in Markdown. Its remote MCP server is another component whose permissions and execution must be controlled; a frontend iframe cannot sandbox that server.

## Host versus app: two different projects

**Near-term evaluation: Desk as an MCP Apps host.** The app renders approved teaching tools inside its own card shell. This requires capability negotiation, a server connection broker, resource validation/caching, isolated rendering, RPC policy and lifecycle cleanup.

**Possible later distribution: Desk tools as MCP Apps for other hosts.** A reviewed explorer could be published for use elsewhere. That does not mean other hosts will implement Desk's ownership, persistent notes or learning evidence rules. Cross-host compatibility must be tested separately.

Do not confuse building an MCP App with implementing a compliant host. The official build guide primarily teaches the former and includes a Vite-based example and coding-agent skill; it does not turn our SPA into a host automatically. [M2]

## Proposed integration shape

```text
Desk-owned card shell (title, provenance, grants, history, fallback)
  ├─ Native renderer: note / worksheet response / example / text
  └─ MCP App adapter
       isolated app view ↔ AppBridge ↔ policy + connection broker
                                              |
                                      approved MCP server
                                              |
                                  bounded domain service/tool

Validated meaningful changes → Desk command service → PostgreSQL revisions
Allowed latest app context → scoped context assembler → next requested tutor turn
```

The logical card record references a renderer binding. A native binding names a registered plugin version. An MCP binding records connection identity, originating tool, UI URI, inspected resource digest where available, protocol/SDK version recorded at implementation, inputs and persistence capability. No connection credential belongs in this record or export.

## Capability mapping

| Need | Standard mechanism / boundary | Desk must add |
|---|---|---|
| Interactive artifact | Tool-linked HTML resource and host mediation [M1] | Native card shell, placement, ownership and fallback. |
| Quiet context updates | `ui/update-model-context` [M5] | Scope checks, provenance, size limits, deduplication, revocation and next-turn policy. |
| Consistent appearance | Host theme/style/dimension information [M6] | Reviewed component kit, visible app boundary, size limits and visual QA. |
| Tool use | Protocol visibility and host-mediated RPC [M3] | Per-connection/per-tool grants, authenticated scope, input checks and rate limits. |
| Network/resources | Resource CSP declarations [M7] | Enforced destination policy, reviewed asset origins and backend network restrictions. |
| Activity restore | Not Desk's persistence contract | Versioned saved state, validated snapshots, no automatic remote mutations on restore. |
| Highlight a plotted object | Not a generic semantic-target guarantee | Optional negotiated Desk learning profile implemented by the app. |
| Assessment | No educational guarantee | Separate attempts, assistance tracking and reviewed evaluator. |

## Proposed Desk learning profile — not an MCP standard

Use a versioned namespaced profile in our adapter/registry for applications that want deeper integration. Specify a schema for: activity instance identity; target catalog; serialisable state and restore capability; meaningful interaction events; source references; assumptions/units/ranges; fallback and accessibility alternatives. Define custom transport only after the spike checks the protocol's extension/capability mechanisms; do not invent standard `ui/*` methods.

A generic compatible app can be offered as an external tool with explicit limitations. A “Desk-integrated” review status additionally requires the profile and tests. Never scrape iframe DOM or guess pixel coordinates to imitate semantic integration.

## Per-view context is not a learning log

Coalesce slider changes. The view's latest context might say that a=2, b=1 and x=-2 currently produce y=-3. It need not trigger a model response. Keep independently meaningful observations/attempts in the host event/history record because context replacement discards prior view updates.

Do not send notebook contents to a tool merely because the tutor can read them. Native note deltas still use NOTES_CONTEXT.md. Data sent by an app is untrusted tool data, not system instructions or a self-attested learner answer. Bound both text and structured fields; neither field is inherently private or safe just because of its name.

## Isolation and permission policy

1. Use an audited host implementation/proxy pattern; app HTML never executes in the top-level React DOM. Authenticate messages against the expected frame, channel and instance. Do not copy illustrative wildcard-message samples without the surrounding validation.
2. App resource CSP lists required connection, asset and embedding origins. The host constructs and enforces the effective policy, can further restrict it, and rejects unapproved resources. An omitted declaration is not permission for arbitrary network access. [M7]
3. Default capabilities exclude camera, microphone, geolocation, clipboard writes, unrelated note reads, plugin installation, credentials, generic filesystem access and cross-server tool access. More power requires an explicitly reviewed use case.
4. Check server-side authorisation independently. MCP visibility metadata and tool annotations are not a complete user-consent or identity system. Bind calls to the active workspace/card and allowlisted server/tool.
5. A remote tool may be side-effecting or server code may be unsafe despite a safe iframe. Review its execution environment and network access. Never run an untrusted MCP server command on the host simply because an app is compatible.
6. Enforce payload/rate/time limits, handle teardown/disconnect, and retain fallback content. Browser iframe isolation alone is not a hard portable CPU/memory quota for hostile computation.
7. Keep provenance, trusted review status and consent outside the app. A malicious app can spoof a consent button inside its own content; it cannot authorise writes to protected learner documents.
8. Treat model context updates as possible prompt injection. They enter a scoped data channel with provenance; subsequent tool actions still undergo independent policy checks.

## Persistence and undo

MCP lifecycle events are not a durable workspace backup. Save the app/engine identity, exact inspected version/digest, schemas, input, selected state, last permitted outputs and fallback in Desk's records. The actual state API is a Desk-profile capability or application-specific service, not automatically provided by generic MCP Apps.

Restore a deterministic first-party explorer without rerunning model generation. For a missing remote service, keep a readable result and state record. Do not automatically invoke an external purchase/send/update operation on reload. Checkpoints cannot undo data already transmitted outside Desk.

## Proposed first experiment

Use only the affine explorer with synthetic data. Build a minimal host and first-party MCP App, ideally sharing pure simulation logic with the native plugin. Test theme/dimensions, parameter input/output, latest-context coalescing, a supported semantic target, state rehydration, blocked note writes, blocked undeclared fetches, rejected tool calls, disconnect and fallback. No real model is needed; inspect the queued context.

Record SDK versions, exact protocol support, working/unsupported features and actual browser tests. A pass establishes one bounded integration, not safety of third-party apps. Compare added code/operational cost against the native path and decide whether to adopt before broad migration.

See ../prompts/CLAUDE_MCP_APPS_SPIKE.md for the separately assignable task.

## v0.4 — independent decision-model experiment

MCP Apps is an interaction/host protocol; System One is a proposed decision-inference capability. Do not mix their contracts. The trusted backend may choose a permitted existing activity; the host then renders that activity through the native renderer or a reviewed MCP adapter. No classifier can approve a new MCP origin, install a plugin or grant note access. The X1 MCP spike and X2 decision spike are independent and separately assigned. Prior source checks in this document date to v0.3; recheck current protocol/SDK compatibility during X1.
