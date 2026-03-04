#!/usr/bin/env bash
# F1: Verify SSE delivery from the backend stream route.
#
# Usage:
#   ./scripts/verify_stream.sh [backend_url]
#
# Defaults to http://127.0.0.1:8000
# Requires: a valid auth token in COLEARNI_TOKEN and workspace id in COLEARNI_WS_ID

set -euo pipefail

BACKEND="${1:-http://127.0.0.1:8000}"
TOKEN="${COLEARNI_TOKEN:?Set COLEARNI_TOKEN to a valid session token}"
WS_ID="${COLEARNI_WS_ID:?Set COLEARNI_WS_ID to a workspace public id}"

URL="${BACKEND}/workspaces/${WS_ID}/chat/respond/stream"

echo "=== F1: Stream Transport Verification ==="
echo "Backend URL: ${URL}"
echo ""

echo "--- Direct backend SSE (curl -N) ---"
echo "Expect: incremental text/event-stream frames arriving before completion"
echo ""

curl -N -s \
  -X POST "${URL}" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"query": "Hello, what can you help me with?"}' \
  --write-out "\n\n--- Response info ---\nHTTP status: %{http_code}\nContent-Type: %{content_type}\nTime to first byte: %{time_starttransfer}s\nTotal time: %{time_total}s\n" \
  2>&1

echo ""
echo "=== Verification complete ==="
echo "Check:"
echo "  1. Status should be 200"
echo "  2. Content-Type should be text/event-stream"
echo "  3. Events should arrive incrementally (not all at once)"
echo "  4. Event sequence: status(thinking) -> status(searching) -> status(responding) -> delta(s) -> status(finalizing) -> final"
