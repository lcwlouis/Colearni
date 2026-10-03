# Separate Claude assignment — MCP Apps feasibility spike X1

This prompt is assigned separately; it is not part of P0. Use the v0.4 package and an isolated experiment directory, preserving existing frontend work. Read AGENTS.md, docs/MCP_APPS.md, docs/PLUGINS.md, docs/INTERACTION_CONTRACT.md, docs/SECURITY_PRIVACY.md and the MCP-specific TEST_PLAN.md cases.

Goal: determine whether a first-party affine-function explorer can run as an MCP App inside a minimal Desk-like host while preserving our context, permission and state boundaries. Do not build the full product or public plugin marketplace.

Consult the live official overview, spec and SDK host examples; inspect/pin exact versions. Distinguish the App SDK from AppBridge host work. The official MCP Apps build guide documents an optional create-mcp-app coding skill; inspect it before installation, and do not install account/global integrations without user approval. A tutorial's Express/Vite server example is not permission to move the Desk domain backend.

Use y=a*x+b with the supplied bounded synthetic inputs. No LLM call or API key is necessary. Prefer shared pure calculation logic with the native fixture. Build a minimal unstyled host harness (not a selected Desk visual design), first-party MCP server and HTML app; document any extra local service. No untrusted remote server commands or arbitrary generated code.

Demonstrate: tool/UI-resource association; capability/version negotiation; correctly isolated view; approved input/result flow; theme/dimensions; permitted parameter updates; latest-context replacement without automatic follow-up; state saved/restored by our adapter; supported semantic highlight; fallback after disconnect.

Test actual browser enforcement of denied undeclared fetch, invalid message, unsupported tool, attempted note read/write, capability escalation and teardown. Native note permissions remain outside the iframe. Host confirmation, not an app-claimed click, is required to import writing. Do not invent standard MCP methods for the optional Desk profile; describe the negotiated implementation separately.

Deliver an adoption report: exact versions, files, commands, screenshots/tests actually run, what the SDK provides, what Desk adds, native-path comparison, operational cost, remaining risks and recommendation. A bounded successful demo is not proof of security for third-party apps. Stop for review; no production integration, commit, deployment, marketplace or automatic installation.
