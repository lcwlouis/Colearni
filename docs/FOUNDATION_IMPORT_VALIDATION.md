# Foundation import — validation and scope

**Date:** 3 October 2026. **Base inspected:** `35bb4f3c9d9c958e79d58f88a915387f3f14c922`.

## Executed checks

The supplied image-free ZIP was safely extracted and the original validator was run successfully with existing Python, jsonschema and TypeScript:

```sh
python docs/foundation/v0.4/tools/validate_pack.py --schema --typecheck
```

Checks cover the exact 61-file manifest, SHA-256 hashes/sizes, UTF-8/no-media contents, Markdown local links/fences/source IDs, JSON parsing, synthetic document/attempt references and arithmetic, graph validation and four negative cases, decision-policy fixtures, proposed navigation status, candidate MCP binding schema and standalone strict TypeScript checks.

The Git tree constructed from the extracted package is `9246a90c764e8e3307aa3a6ffab5f34391cf3577`. The uploaded snapshot tree matches exactly, including every file and its contents. These checks apply within the snapshot; repository adoption notes are intentionally outside its immutable manifest.

## Limits

No application dependencies, app/Storybook builds, browser/device tests, CI result, database migration, provider call, security audit, licence audit or source-ledger revalidation is claimed. Direct container cloning was unavailable because GitHub DNS resolution failed; repository reads and updates used the connected GitHub API instead. The existing P0 test/audit results in root PROGRESS.md are historical reports, not rerun results.

No application source, runtime contracts/fixtures, lockfile, package manifest, tool configuration or pre-existing progress history is changed. New TypeScript/JSON/Python files are source-package reference materials under docs/foundation/v0.4, not imported application modules. Standard repository checks should still be run in the normal development/CI environment before merge.

This change is a documentation PR. Publishing it does not merge it, deploy Desk, approve visuals or activate any experiment.
