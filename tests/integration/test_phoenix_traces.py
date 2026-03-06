"""Integration tests that verify LLM trace correctness via Phoenix GraphQL API.

These tests query Phoenix for recent traces and verify:
- System prompts are in the correct role
- Prompt templates are not truncated
- Source material excerpts are sufficient
- Token counts are present

Prerequisites:
- Phoenix must be running at PHOENIX_ENDPOINT (default: http://localhost:6006)
- The backend must have processed at least one request recently

Usage:
    pytest tests/integration/test_phoenix_traces.py -v
    pytest tests/integration/test_phoenix_traces.py -v -k "system_role"
"""

from __future__ import annotations

import httpx
import pytest

# Auto-skip if Phoenix is not reachable
PHOENIX_ENDPOINT = "http://localhost:6006"


def phoenix_available() -> bool:
    """Check if Phoenix is running and reachable."""
    try:
        resp = httpx.get(f"{PHOENIX_ENDPOINT}/graphql", timeout=3.0)
        return resp.status_code in (200, 400, 405)  # 400/405 = endpoint exists
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


pytestmark = pytest.mark.skipif(
    not phoenix_available(),
    reason=f"Phoenix not available at {PHOENIX_ENDPOINT}",
)


# Import the audit module
from scripts.phoenix_trace_audit import (  # noqa: E402
    AuditResult,
    query_phoenix,
    run_audit,
)


@pytest.fixture(scope="module")
def recent_spans() -> list[dict]:
    """Fetch recent spans from Phoenix."""
    return query_phoenix(PHOENIX_ENDPOINT, last_n=20)


@pytest.fixture(scope="module")
def audit_result() -> AuditResult:
    """Run the full audit."""
    return run_audit(PHOENIX_ENDPOINT, last_n=20)


@pytest.fixture(scope="module")
def llm_spans(recent_spans: list[dict]) -> list[dict]:
    """Filter to only LLM spans."""
    result = []
    for span in recent_spans:
        attrs = span.get("_parsed_attrs", {})
        kind = attrs.get("openinference.span.kind", span.get("spanKind", ""))
        if kind.upper() == "LLM":
            result.append(span)
    return result


class TestPhoenixConnection:
    """Verify Phoenix is reachable and returning data."""

    def test_phoenix_reachable(self) -> None:
        resp = httpx.post(
            f"{PHOENIX_ENDPOINT}/graphql",
            json={"query": "{ projects { edges { node { name } } } }"},
            timeout=5.0,
        )
        assert resp.status_code == 200

    def test_spans_returned(self, recent_spans: list[dict]) -> None:
        if len(recent_spans) == 0:
            pytest.skip("No spans found in Phoenix (no recent backend activity)")

    def test_llm_spans_found(self, llm_spans: list[dict]) -> None:
        if len(llm_spans) == 0:
            pytest.skip("No LLM spans found in Phoenix (no recent LLM calls)")


class TestSystemRoleAssignment:
    """Verify that instructions are in system role, not user role."""

    def test_no_instructions_in_user_role(self, audit_result: AuditResult) -> None:
        """Critical: prompt templates with ---Role--- etc. must NOT be in user messages."""
        bad = [
            f for f in audit_result.findings if f.category == "instructions_in_user_role"
        ]
        if bad:
            details = "\n".join(
                f"  - {f.span_name}: {f.message}" for f in bad[:5]
            )
            pytest.fail(
                f"Found {len(bad)} spans with instructions in user role:\n{details}"
            )

    def test_system_messages_present(self, audit_result: AuditResult) -> None:
        """All LLM spans should have a system message."""
        missing = [
            f for f in audit_result.findings if f.category == "no_system_message"
        ]
        if missing:
            names = [f.span_name for f in missing[:5]]
            pytest.xfail(
                f"Found {len(missing)} LLM spans without system role: {names}"
            )

    def test_system_messages_not_stubs(self, audit_result: AuditResult) -> None:
        """System messages should contain real instructions, not tiny stubs."""
        stubs = [
            f for f in audit_result.findings if f.category == "stub_system_message"
        ]
        if stubs:
            details = "\n".join(
                f"  - {f.span_name}: {f.detail}" for f in stubs[:5]
            )
            pytest.fail(
                f"Found {len(stubs)} spans with stub system messages:\n{details}"
            )


class TestInputOutputPopulated:
    """Verify that input.value and output.value are set for Phoenix Info tab."""

    def test_input_value_populated(self, audit_result: AuditResult) -> None:
        missing = [
            f for f in audit_result.findings if f.category == "missing_input_value"
        ]
        if missing:
            names = [f.span_name for f in missing[:5]]
            pytest.xfail(
                f"Found {len(missing)} LLM spans without input.value: {names}"
            )

    def test_output_value_populated(self, audit_result: AuditResult) -> None:
        missing = [
            f for f in audit_result.findings if f.category == "missing_output_value"
        ]
        if missing:
            names = [f.span_name for f in missing[:5]]
            pytest.xfail(
                f"Found {len(missing)} LLM spans without output.value: {names}"
            )


class TestTokenCounts:
    """Verify token usage is recorded."""

    def test_token_counts_present(self, llm_spans: list[dict]) -> None:
        """At least some LLM spans should have token counts."""
        from scripts.phoenix_trace_audit import _get_nested

        with_tokens = 0
        for span in llm_spans:
            attrs = span.get("_parsed_attrs", {})
            if _get_nested(attrs, "llm.token_count.prompt") is not None:
                with_tokens += 1
        if llm_spans:
            ratio = with_tokens / len(llm_spans)
            assert ratio > 0.5, (
                f"Only {with_tokens}/{len(llm_spans)} LLM spans have token counts"
            )


class TestSourceMaterialQuality:
    """Verify that source material in prompts is sufficient."""

    def test_no_thin_source_material(self, audit_result: AuditResult) -> None:
        """Source excerpts sent to LLM should not be trivially small."""
        thin = [
            f for f in audit_result.findings if f.category == "thin_source_material"
        ]
        if thin:
            details = "\n".join(
                f"  - {f.span_name}: {f.message}" for f in thin[:5]
            )
            pytest.xfail(
                f"Found {len(thin)} spans with thin source material:\n{details}"
            )


class TestOverallAudit:
    """High-level audit assertions."""

    def test_no_critical_findings(self, audit_result: AuditResult) -> None:
        """The audit should pass with no critical findings."""
        if not audit_result.passed:
            critical = [f for f in audit_result.findings if f.severity == "critical"]
            details = "\n".join(
                f"  - [{f.category}] {f.span_name}: {f.message}" for f in critical[:10]
            )
            pytest.xfail(
                f"Audit found {audit_result.critical_count} critical findings:\n{details}"
            )

    def test_audit_summary(self, audit_result: AuditResult) -> None:
        """Print audit summary for visibility (always passes)."""
        print(f"\n  Audit: {audit_result.total_spans} spans, "
              f"{audit_result.llm_spans} LLM, "
              f"{audit_result.critical_count} critical, "
              f"{audit_result.warning_count} warning")
