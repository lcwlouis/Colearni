"""Tests for evidence planner (AR2.1)."""

from __future__ import annotations

from domain.retrieval.evidence_planner import (
    EvidencePlan,
    build_evidence_plan,
)


class TestEvidencePlanConstruction:
    """Verify EvidencePlan dataclass and build_evidence_plan factory."""

    def test_no_retrieval_plan(self):
        plan = build_evidence_plan(
            base_query="hello",
            workspace_id=1,
            needs_retrieval=False,
        )
        assert plan.stop_reason == "no_retrieval_needed"
        assert plan.retrieval_budget == 0
        assert not plan.needs_retrieval

    def test_basic_plan_with_concept(self):
        plan = build_evidence_plan(
            base_query="explain photosynthesis",
            workspace_id=42,
            needs_retrieval=True,
            top_k=15,
            concept_id=7,
        )
        assert plan.base_query == "explain photosynthesis"
        assert plan.workspace_id == 42
        assert plan.retrieval_budget == 15
        assert plan.candidate_concept_ids == [7]
        assert plan.graph_root_concept_id == 7
        assert plan.needs_retrieval
        assert plan.stop_reason == "initial"

    def test_basic_plan_without_concept(self):
        plan = build_evidence_plan(
            base_query="what is this about?",
            workspace_id=1,
            needs_retrieval=True,
        )
        assert plan.candidate_concept_ids == []
        assert plan.graph_root_concept_id is None
        assert plan.retrieval_budget == 20  # default

    def test_expansion_flags_default_off(self):
        plan = build_evidence_plan(
            base_query="q",
            workspace_id=1,
            needs_retrieval=True,
        )
        assert not plan.expand_graph_neighbors
        assert plan.graph_hop_budget == 0
        assert not plan.expand_document_summaries
        assert plan.subqueries == []
        assert plan.provenance_linked_chunk_ids == []


class TestEvidencePlanWithResults:
    """Verify with_results produces correct immutable copies."""

    def test_with_results_coverage_sufficient(self):
        plan = build_evidence_plan(
            base_query="q",
            workspace_id=1,
            needs_retrieval=True,
            top_k=20,
        )
        updated = plan.with_results(
            stop_reason="coverage_sufficient",
            retrieved_chunk_count=5,
        )
        assert updated.stop_reason == "coverage_sufficient"
        assert updated.retrieved_chunk_count == 5
        assert not updated.budget_exhausted
        # Original unchanged
        assert plan.stop_reason == "initial"
        assert plan.retrieved_chunk_count == 0

    def test_with_results_budget_exhausted(self):
        plan = build_evidence_plan(
            base_query="q",
            workspace_id=1,
            needs_retrieval=True,
            top_k=10,
        )
        updated = plan.with_results(
            stop_reason="budget_exhausted",
            retrieved_chunk_count=10,
        )
        assert updated.stop_reason == "budget_exhausted"
        assert updated.budget_exhausted

    def test_with_results_preserves_fields(self):
        plan = build_evidence_plan(
            base_query="photosynthesis",
            workspace_id=5,
            needs_retrieval=True,
            top_k=15,
            concept_id=42,
        )
        updated = plan.with_results(
            stop_reason="coverage_sufficient",
            retrieved_chunk_count=8,
        )
        assert updated.base_query == "photosynthesis"
        assert updated.workspace_id == 5
        assert updated.retrieval_budget == 15
        assert updated.candidate_concept_ids == [42]
        assert updated.graph_root_concept_id == 42

    def test_empty_workspace_stop_reason(self):
        plan = build_evidence_plan(
            base_query="q",
            workspace_id=1,
            needs_retrieval=True,
        )
        updated = plan.with_results(
            stop_reason="empty_workspace",
            retrieved_chunk_count=0,
        )
        assert updated.stop_reason == "empty_workspace"
        assert updated.needs_retrieval  # plan itself wanted retrieval


class TestBudgetExhausted:
    """Verify budget_exhausted property."""

    def test_under_budget(self):
        plan = EvidencePlan(
            base_query="q",
            workspace_id=1,
            retrieval_budget=20,
            retrieved_chunk_count=10,
        )
        assert not plan.budget_exhausted

    def test_at_budget(self):
        plan = EvidencePlan(
            base_query="q",
            workspace_id=1,
            retrieval_budget=20,
            retrieved_chunk_count=20,
        )
        assert plan.budget_exhausted

    def test_over_budget(self):
        plan = EvidencePlan(
            base_query="q",
            workspace_id=1,
            retrieval_budget=10,
            retrieved_chunk_count=15,
        )
        assert plan.budget_exhausted
