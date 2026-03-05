#!/usr/bin/env python3
"""Phoenix trace audit — programmatic verification of LLM trace correctness.

Queries Phoenix's GraphQL API to verify that LLM spans have:
- System prompts in the correct role (not stuffed into user)
- Non-trivial system messages (>200 chars, not just a stub)
- input.value and output.value populated for Phoenix Info tab
- Token counts present and reasonable
- No truncated prompts

Usage:
    python scripts/phoenix_trace_audit.py                    # defaults
    python scripts/phoenix_trace_audit.py --last-n 20        # check last 20 spans
    python scripts/phoenix_trace_audit.py --endpoint http://localhost:6006
    python scripts/phoenix_trace_audit.py --json             # machine-readable output
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "http://localhost:6006"
GRAPHQL_PATH = "/graphql"

# Thresholds
MIN_SYSTEM_MSG_LENGTH = 100  # system message must be meaningful
STUB_SYSTEM_MSG_LENGTH = 50  # below this = definitely a stub
MIN_PROMPT_TOKENS = 10  # sanity check on token counts


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class Finding:
    """A single audit finding."""

    span_name: str
    span_id: str
    severity: str  # "critical" | "warning" | "info"
    category: str
    message: str
    detail: str = ""


@dataclass
class AuditResult:
    """Aggregated audit results."""

    total_spans: int = 0
    llm_spans: int = 0
    findings: list[Finding] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")

    @property
    def passed(self) -> bool:
        return self.critical_count == 0


# ---------------------------------------------------------------------------
# GraphQL query
# ---------------------------------------------------------------------------
SPANS_QUERY = """
query RecentSpans($first: Int!) {
  projects {
    edges {
      node {
        name
        spans(first: $first, sort: { col: startTime, dir: desc }) {
          edges {
            node {
              name
              spanKind
              statusCode
              startTime
              latencyMs
              context {
                traceId
                spanId
              }
              attributes
            }
          }
        }
      }
    }
  }
}
"""


def query_phoenix(endpoint: str, last_n: int) -> list[dict[str, Any]]:
    """Query Phoenix GraphQL for recent spans."""
    url = f"{endpoint}{GRAPHQL_PATH}"
    payload = {"query": SPANS_QUERY, "variables": {"first": last_n}}

    try:
        resp = httpx.post(url, json=payload, timeout=10.0)
        resp.raise_for_status()
    except httpx.ConnectError:
        logger.error("Cannot connect to Phoenix at %s", url)
        raise SystemExit(1)
    except httpx.HTTPStatusError as exc:
        logger.error("Phoenix returned %s: %s", exc.response.status_code, exc.response.text[:200])
        raise SystemExit(1)

    data = resp.json()
    if "errors" in data:
        logger.error("GraphQL errors: %s", data["errors"])
        raise SystemExit(1)

    spans: list[dict[str, Any]] = []
    for project_edge in data.get("data", {}).get("projects", {}).get("edges", []):
        project = project_edge["node"]
        for span_edge in project.get("spans", {}).get("edges", []):
            span = span_edge["node"]
            # Parse attributes JSON string
            attrs_raw = span.get("attributes") or "{}"
            if isinstance(attrs_raw, str):
                try:
                    span["_parsed_attrs"] = json.loads(attrs_raw)
                except json.JSONDecodeError:
                    span["_parsed_attrs"] = {}
            else:
                span["_parsed_attrs"] = attrs_raw
            span["_project"] = project["name"]
            spans.append(span)
    return spans


# ---------------------------------------------------------------------------
# Audit checks
# ---------------------------------------------------------------------------
def _get_nested(attrs: dict[str, Any], dotted_key: str) -> Any:
    """Get a value from nested dicts using a dotted key path.

    Phoenix stores attributes as nested dicts: ``llm.input_messages``
    becomes ``attrs["llm"]["input_messages"]``.
    """
    parts = dotted_key.split(".")
    current: Any = attrs
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _parse_messages(attrs: dict[str, Any]) -> list[dict[str, str]] | None:
    """Extract input messages from attributes.

    Supports two formats:
    - **Flattened (OpenInference)**: ``llm.input_messages`` is a dict with
      numeric keys, each containing ``message.role`` / ``message.content``.
    - **Legacy JSON string**: ``llm.input_messages`` is a JSON-encoded list
      of ``{"role": ..., "content": ...}`` dicts.
    """
    raw = _get_nested(attrs, "llm.input_messages")
    if not raw:
        return None
    # Flattened format: dict with numeric string keys ("0", "1", ...)
    if isinstance(raw, dict):
        messages: list[dict[str, str]] = []
        for key in sorted(raw.keys(), key=lambda k: int(k) if k.isdigit() else float("inf")):
            if not key.isdigit():
                continue
            entry = raw[key]
            if isinstance(entry, dict):
                msg_data = entry.get("message", entry)
                messages.append({
                    "role": str(msg_data.get("role", "")),
                    "content": str(msg_data.get("content", "")),
                })
        return messages if messages else None
    # Legacy: JSON string
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # May be truncated at _MAX_VALUE_CHARS — try to salvage partial data
            try:
                last_bracket = raw.rfind("}]")
                if last_bracket > 0:
                    return json.loads(raw[: last_bracket + 2])
            except (json.JSONDecodeError, ValueError):
                pass
            return None
    if isinstance(raw, list):
        return raw
    return None


def _parse_input_value(input_value: str) -> list[dict[str, str]] | None:
    """Parse input.value text with [system]/[user] markers into messages.

    The ``set_input_output`` helper in observability.py formats messages as::

        [system]
        <content>

        [user]
        <content>
    """
    import re

    pattern = re.compile(r"\[(system|user|assistant)\]\n", re.IGNORECASE)
    parts = pattern.split(input_value)
    if len(parts) < 3:
        return None

    messages: list[dict[str, str]] = []
    # parts[0] is text before first marker (usually empty)
    # then alternating: role, content, role, content, ...
    i = 1
    while i < len(parts) - 1:
        role = parts[i].lower()
        content = parts[i + 1].strip()
        messages.append({"role": role, "content": content})
        i += 2
    return messages if messages else None


def audit_span(span: dict[str, Any]) -> list[Finding]:
    """Run all audit checks on a single span."""
    findings: list[Finding] = []
    attrs = span.get("_parsed_attrs", {})
    span_name = span.get("name", "unknown")
    span_id = span.get("context", {}).get("spanId", "unknown")
    span_kind = _get_nested(attrs, "openinference.span.kind") or span.get("spanKind", "")

    # Only audit LLM spans in depth (handle case variations)
    if span_kind.upper() != "LLM":
        return findings

    # --- Check 1: input.value populated ---
    input_value = _get_nested(attrs, "input.value") or ""
    if not input_value:
        findings.append(Finding(
            span_name=span_name,
            span_id=span_id,
            severity="warning",
            category="missing_input_value",
            message="input.value is empty — Phoenix Info tab will be blank",
        ))

    # --- Check 2: output.value populated ---
    output_value = _get_nested(attrs, "output.value") or ""
    if not output_value:
        findings.append(Finding(
            span_name=span_name,
            span_id=span_id,
            severity="warning",
            category="missing_output_value",
            message="output.value is empty — Phoenix Info tab won't show response",
        ))

    # --- Check 3: Parse input messages and check roles ---
    messages = _parse_messages(attrs)
    raw_msgs = _get_nested(attrs, "llm.input_messages")
    if raw_msgs and isinstance(raw_msgs, str):
        try:
            json.loads(raw_msgs)
        except json.JSONDecodeError:
            findings.append(Finding(
                span_name=span_name,
                span_id=span_id,
                severity="warning",
                category="truncated_input_messages",
                message=f"llm.input_messages JSON is truncated at {len(raw_msgs)} chars (likely _MAX_VALUE_CHARS limit)",
            ))

    # Fallback: use input.value which has [system]/[user] markers
    if messages is None and input_value:
        messages = _parse_input_value(input_value)

    if messages is None:
        findings.append(Finding(
            span_name=span_name,
            span_id=span_id,
            severity="warning",
            category="missing_input_messages",
            message="llm.input_messages is missing or unparseable",
        ))
    else:
        system_msgs = [m for m in messages if m.get("role") == "system"]
        user_msgs = [m for m in messages if m.get("role") == "user"]

        # Check 3a: At least one system message
        if not system_msgs:
            findings.append(Finding(
                span_name=span_name,
                span_id=span_id,
                severity="critical",
                category="no_system_message",
                message="No system role message found — all instructions in user role",
            ))

        # Check 3b: System message is not a stub
        for i, msg in enumerate(system_msgs):
            content = str(msg.get("content", ""))
            if len(content) < STUB_SYSTEM_MSG_LENGTH:
                findings.append(Finding(
                    span_name=span_name,
                    span_id=span_id,
                    severity="critical",
                    category="stub_system_message",
                    message=f"System message [{i}] is a stub ({len(content)} chars)",
                    detail=content[:200],
                ))
            elif len(content) < MIN_SYSTEM_MSG_LENGTH:
                findings.append(Finding(
                    span_name=span_name,
                    span_id=span_id,
                    severity="warning",
                    category="short_system_message",
                    message=f"System message [{i}] is short ({len(content)} chars)",
                    detail=content[:200],
                ))

        # Check 3c: Instructions leak — prompt templates in user role
        for i, msg in enumerate(user_msgs):
            content = str(msg.get("content", ""))
            instruction_markers = [
                "---Role---",
                "---Goal---",
                "---Non-negotiable rules---",
                "---Output contract---",
                "---Failure behavior---",
            ]
            found_markers = [m for m in instruction_markers if m in content]
            if found_markers:
                findings.append(Finding(
                    span_name=span_name,
                    span_id=span_id,
                    severity="critical",
                    category="instructions_in_user_role",
                    message=f"Prompt template markers found in user message [{i}]: {found_markers}",
                    detail=f"First 300 chars: {content[:300]}",
                ))

    # --- Check 4: Token counts ---
    prompt_tokens = _get_nested(attrs, "llm.token_count.prompt")
    completion_tokens = _get_nested(attrs, "llm.token_count.completion")
    if prompt_tokens is None and completion_tokens is None:
        findings.append(Finding(
            span_name=span_name,
            span_id=span_id,
            severity="info",
            category="missing_token_counts",
            message="No token counts recorded",
        ))
    elif prompt_tokens is not None and int(prompt_tokens) < MIN_PROMPT_TOKENS:
        findings.append(Finding(
            span_name=span_name,
            span_id=span_id,
            severity="warning",
            category="low_prompt_tokens",
            message=f"Suspiciously low prompt token count: {prompt_tokens}",
        ))

    # --- Check 5: Truncation markers ---
    if input_value:
        truncation_patterns = ["... (len=", "…(truncated)", "[TRUNCATED]"]
        for pat in truncation_patterns:
            if pat in input_value:
                findings.append(Finding(
                    span_name=span_name,
                    span_id=span_id,
                    severity="warning",
                    category="truncated_content",
                    message=f"Possible truncation marker in input: '{pat}'",
                ))
                break

    # --- Check 6: Source material quality (for tutor/quiz spans) ---
    if messages:
        for msg in messages:
            content = str(msg.get("content", ""))
            if "SOURCE_MATERIAL_EXCERPTS:" in content or "DOCUMENT_SUMMARIES:" in content:
                # Check if the source material is suspiciously small
                source_start = content.find("SOURCE_MATERIAL_EXCERPTS:")
                if source_start == -1:
                    source_start = content.find("DOCUMENT_SUMMARIES:")
                if source_start >= 0:
                    source_section = content[source_start:]
                    # Check for very short source sections
                    if len(source_section) < 200:
                        findings.append(Finding(
                            span_name=span_name,
                            span_id=span_id,
                            severity="warning",
                            category="thin_source_material",
                            message=f"Source material section is only {len(source_section)} chars",
                            detail=source_section[:300],
                        ))

    return findings


def run_audit(endpoint: str, last_n: int) -> AuditResult:
    """Run the full audit against Phoenix."""
    spans = query_phoenix(endpoint, last_n)
    result = AuditResult(total_spans=len(spans))

    for span in spans:
        attrs = span.get("_parsed_attrs", {})
        span_kind = _get_nested(attrs, "openinference.span.kind") or span.get("spanKind", "")
        if span_kind.upper() == "LLM":
            result.llm_spans += 1
        span_findings = audit_span(span)
        result.findings.extend(span_findings)

    return result


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------
def format_text(result: AuditResult) -> str:
    """Format audit results as human-readable text."""
    lines = [
        "=" * 60,
        "  Phoenix Trace Audit Report",
        "=" * 60,
        f"  Spans checked: {result.total_spans} total, {result.llm_spans} LLM",
        f"  Findings: {result.critical_count} critical, {result.warning_count} warning",
        f"  Status: {'PASS' if result.passed else 'FAIL'}",
        "=" * 60,
    ]

    if not result.findings:
        lines.append("\n  ✅ No issues found.\n")
        return "\n".join(lines)

    # Group by severity
    for severity in ("critical", "warning", "info"):
        sev_findings = [f for f in result.findings if f.severity == severity]
        if not sev_findings:
            continue
        icon = {"critical": "❌", "warning": "⚠️", "info": "ℹ️"}.get(severity, "?")
        lines.append(f"\n  {icon} {severity.upper()} ({len(sev_findings)})")
        lines.append("  " + "-" * 40)
        for f in sev_findings:
            lines.append(f"  [{f.category}] {f.span_name} (span:{f.span_id[:8]})")
            lines.append(f"    {f.message}")
            if f.detail:
                lines.append(f"    Detail: {f.detail[:120]}...")
            lines.append("")

    return "\n".join(lines)


def format_json(result: AuditResult) -> str:
    """Format audit results as JSON."""
    return json.dumps(
        {
            "total_spans": result.total_spans,
            "llm_spans": result.llm_spans,
            "critical_count": result.critical_count,
            "warning_count": result.warning_count,
            "passed": result.passed,
            "findings": [
                {
                    "span_name": f.span_name,
                    "span_id": f.span_id,
                    "severity": f.severity,
                    "category": f.category,
                    "message": f.message,
                    "detail": f.detail,
                }
                for f in result.findings
            ],
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Phoenix LLM traces")
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help=f"Phoenix endpoint (default: {DEFAULT_ENDPOINT})",
    )
    parser.add_argument(
        "--last-n",
        type=int,
        default=10,
        help="Number of recent spans to audit (default: 10)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output as JSON",
    )
    parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="Exit with code 1 if critical findings exist",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    result = run_audit(args.endpoint, args.last_n)

    if args.json_output:
        print(format_json(result))
    else:
        print(format_text(result))

    if args.fail_on_critical and not result.passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
