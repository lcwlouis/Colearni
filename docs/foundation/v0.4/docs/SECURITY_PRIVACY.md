# Security and privacy requirements

This is a threat-informed requirements list, not a security audit or compliance certificate.

## Protected assets

Learner notes and responses, uploaded sources, model credentials, research disclosures, identity/membership, persistent revisions and backups, and trusted agent/plugin permissions. Local self-hosting does not mean external models receive no data; provider-bound information must be disclosed.

## Required boundaries

- Identity and workspace authorisation are enforced server-side for every read/write/download/tool call. A UUID in a URL is not access control.
- Learner documents and sharing have owner-only mutation paths. App/tutor suggestions remain separate until host-owned acceptance.
- Scope permissions apply before source/note indexing, cache retrieval, model dispatch, research queries and app/tool inputs. Derived content retains provenance for revocation.
- Secrets stay out of browser bundles, iframe messages, logs, Storybook fixtures and exports. No unrestricted credentials to plugins. [R11]
- Sanitize rendered Markdown/HTML and allowlist links/media. Remote images can cause outbound requests; downloading/rendering requires a deliberate policy.
- Ingestion restricts file sizes, content types, parser cost and access. Research/download clients defend against private-network and metadata-service fetches, redirects and malformed files.
- Extracted text, notes, plugin catalog entries and app model-context requests are untrusted data. Prompt wording is not an authorisation boundary. [R9]
- MCP view isolation, CSP and broker allowlists protect a distinct executable interface. The server behind the view also needs review and resource/network constraints. See MCP_APPS.md.
- Snapshot/restore respects current permissions and never repeats external side effects automatically.

## Minimal privacy controls

Disclosed desk-level tutor-read default; explicit private note override; read-sharing on reuse; “Used from your notes” provenance; cancellation; content export/deletion; provider connection and outgoing-data explanation. No unsolicited critique while typing. Permissions for tutor reading, external search disclosure, plugin inputs, public sharing and human collaboration are distinct.

Revocation prevents future use and invalidates derived context. It cannot recall information already transmitted. Backups/exports are separate copies with their own retention; explain these limits before claiming deletion.

## Self-hosted deployment

Bind the initial local service to loopback by default. Do not expose PostgreSQL publicly. Avoid host Docker socket, privileged containers and whole-home mounts. Use dedicated export directories. Authentication/bootstrap and browser-origin protection are required even when “local”; local storage is not automatically immune to malicious web origins or shared-machine access. LAN/public exposure requires a reviewed profile with authentication, TLS and network policy.

## School/minor gate

Free educational licensing is not readiness for children or school deployment. Before that audience: define roles, administrator access, consent/age rules, retention/deletion, provider contracts/data location, incident response and safeguarding. Select applicable jurisdiction with qualified review. The early pilot should not silently expand to minors.

## Logging and cost

Log request IDs, statuses, durations, permission decisions and resource consumption. Avoid raw private content and keys by default. Restrict debug retention and access. Bound inference/research jobs and retries. Expose estimates as estimates, not guaranteed charges.

## Release blockers

Unauthorised note access/write; cross-workspace data leak; silent draft loss; secrets exposed in browser/export; unreviewed executable host access; unsafe restore; unlabelled synthetic/fabricated evidence; lack of tested backup recovery. A visually polished screen does not waive these tests.

## v0.4 — decision model boundaries

Decision-model outputs are untrusted proposals. The server filters context and allowed options before dispatch, validates returned values, rechecks permissions/revisions and enforces budgets. Model confidence never grants access, approves public exports or authorises plugin execution. A classifier is not the security boundary against malicious instructions.

New remote processors require explicit configuration and a reviewed data path. Local-only configuration must never silently fail over to a hosted classifier. Treat model telemetry as potentially sensitive; redact content by default. An opt-in local runtime remains distinct from the app/database container setup. See [DECISION_LAYER.md](DECISION_LAYER.md).
