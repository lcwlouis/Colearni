# Self-hosting, files and portability

## Accepted deployment direction

One Docker Compose package starts the product; the user does not install PostgreSQL separately. Proposed initial services are an app container serving the built frontend/API and a PostgreSQL container. Workers or an optional MCP sidecar can be added as profiled requirements rather than hidden mandatory services. Compose coordinates services, networks and volumes. [D1]

There is no runnable Compose file or published Desk image in this documentation package. Image versions, bootstrap/authentication, health checks and upgrade commands must be implemented and tested before promising one-command installation.

## Storage split

Use a named volume for PostgreSQL internals and private application storage for assets. Docker-managed volumes persist separately from replaceable containers, but should not be presented as a normal Markdown notebook directory. [D2]

Use an optional dedicated bind-mounted host folder for readable exports/backups. A bind mount exposes an actual Docker-host folder; on a remote installation it is not the student's local laptop folder. Give remote users authenticated download instead. [D3]

```text
Desk Library/                 # proposed user-visible export folder
  notes/                      # readable Markdown
  worksheets/                 # readable attempts/examples
  attachments/                # selected authorised assets
  backups/                    # private restorable packages
  export-manifest.json        # version, cutoff, IDs, losses, provenance
```

PostgreSQL is authoritative. Exporting is a product operation, not a filesystem mount trick. External edits are not automatically imported; live two-way folder sync is deferred. Do not overwrite external edits silently during refresh. No generic “Open folder on your laptop” promise from a remote web page.

## Three distinct export modes

**Readable collection:** Markdown and assets a learner can use outside Desk. Include stable links/IDs and provenance where practical; report unsupported interactive semantics.

**Private restorable backup:** versioned structured data, document and task revisions, attempt/feedback relationships, source/asset manifest, meaningful activity state and required engine references. Includes sensitive learning data. Encrypt/protect backups according to the deployment design. Credentials and provider sessions are excluded from ordinary user exports and reconfigured on restore.

**Public sharing:** explicit sanitised learning structures and permitted engine/source material. Never reuse the full private-backup path as a public publishing shortcut. Imported packages do not automatically grant note access or execute/install plugins.

## Backup consistency

Use PostgreSQL-supported logical/physical backup procedures appropriate to the release. `pg_dump` provides a consistent database snapshot; assets outside the database require coordinated treatment. [D4]

For the first deployment, use a documented maintenance/quiesce window or immutable asset revision manifest with garbage collection paused while the manifest is captured. Record app/schema/plugin versions and cutoff. Verify referenced hashes/bytes. A background file copy from a running PG data directory is not the default backup design.

## Restore acceptance

Export → fresh isolated installation → validate manifest/version/paths/sizes → restore data and assets without executing imported code → re-establish current owners/grants → compare note content, links, origins, task revisions and selected tool state. Report missing plugins or inaccessible sources using fallbacks. Test malformed archives, path traversal, duplicate IDs, unsupported versions, credentials accidentally included and insufficient storage.

## Upgrades and recovery

Pin compatible service images; document migration prechecks, backups and rollback limits. Do not instruct ordinary users to delete volumes as troubleshooting. Test restart, container replacement and version upgrades with learner data. Implement purge/retention decisions for abandoned exports and private history before production.

## Product promise boundaries

Self-hosted is not automatically local-first, offline, end-to-end encrypted or zero-cost. External models/research receive approved inputs, and the user bears provider/hardware costs unless the managed service covers them. Notes should remain readable/exportable when a model is unavailable. Do not require a Desk-cloud account merely to inspect local learning data in the intended self-hosted product.

## v0.4 — optional local decision service

The accepted simple install remains bundled Docker Compose with an app and PostgreSQL, persistent internals and an explicit readable export folder. Do not add a mandatory decision runtime. A later opt-in local-model profile needs documented model licensing, memory/compute requirements and lifecycle handling. Hosted candidates remain optional backend integrations. No transparent cloud fallback from local-only policy is allowed. The app must still work with decision inference disabled.
