"""Tests for evidence planner (AR2.1 / AR2.2)."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

from domain.retrieval.evidence_planner import (
    EvidencePlan,
    _coverage_sufficient,
    _expand_graph_neighbors,
    _merge_chunks,
    _plan_follow_up_subqueries,
    build_evidence_plan,
    execute_evidence_plan,
)
from domain.retrieval.types import RankedChunk


def _make_chunk(chunk_id: int, score: float = 0.5) -> RankedChunk:
    return RankedChunk(
        workspace_id=1,
        document_id=1,
        chunk_id=chunk_id,
        chunk_index=0,
        text=f"chunk-{chunk_id}",
        score=score,
        retrieval_method="hybrid",
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
        assert plan.expand_document_summaries  # always on since AR2.3
        assert plan.provenance_linked_chunk_ids == []

    def test_subquery_from_concept_name(self):
        plan = build_evidence_plan(
            base_query="how does it work?",
            workspace_id=1,
            needs_retrieval=True,
            concept_name="Photosynthesis",
        )
        assert plan.subqueries == ["Photosynthesis"]
        assert plan.concept_name == "Photosynthesis"

    def test_no_subquery_when_concept_in_query(self):
        plan = build_evidence_plan(
            base_query="explain photosynthesis in detail",
            workspace_id=1,
            needs_retrieval=True,
            concept_name="Photosynthesis",
        )
        assert plan.subqueries == []

    def test_max_retrieval_passes_default(self):
        plan = build_evidence_plan(
            base_query="q",
            workspace_id=1,
            needs_retrieval=True,
        )
        assert plan.max_retrieval_passes == 2


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
            retrieval_passes_used=1,
        )
        assert updated.stop_reason == "coverage_sufficient"
        assert updated.retrieved_chunk_count == 5
        assert updated.retrieval_passes_used == 1
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
            concept_name="Photosynthesis",
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
        assert updated.concept_name == "Photosynthesis"

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


class TestFollowUpSubqueries:
    """Verify _plan_follow_up_subqueries helper."""

    def test_concept_name_generates_subquery(self):
        subs = _plan_follow_up_subqueries(
            base_query="how does it work?",
            concept_name="Photosynthesis",
        )
        assert subs == ["Photosynthesis"]

    def test_no_subquery_when_name_in_query(self):
        subs = _plan_follow_up_subqueries(
            base_query="explain photosynthesis",
            concept_name="Photosynthesis",
        )
        assert subs == []

    def test_no_subquery_without_concept(self):
        subs = _plan_follow_up_subqueries(
            base_query="hello",
            concept_name=None,
        )
        assert subs == []

    def test_neighbor_names_added_as_subqueries(self):
        subs = _plan_follow_up_subqueries(
            base_query="how does it work?",
            concept_name="Photosynthesis",
            neighbor_names=["Chloroplast", "Light Reactions"],
        )
        assert subs == ["Photosynthesis", "Chloroplast", "Light Reactions"]

    def test_neighbor_names_skipped_when_in_query(self):
        subs = _plan_follow_up_subqueries(
            base_query="explain chloroplast",
            concept_name=None,
            neighbor_names=["Chloroplast", "Thylakoid"],
        )
        assert subs == ["Thylakoid"]


class TestCoverageSufficient:
    """Verify _coverage_sufficient helper."""

    def test_below_min_chunks(self):
        chunks = [_make_chunk(1, 0.9), _make_chunk(2, 0.9)]
        assert not _coverage_sufficient(chunks)

    def test_low_score(self):
        chunks = [_make_chunk(i, 0.1) for i in range(5)]
        assert not _coverage_sufficient(chunks)

    def test_good_coverage(self):
        chunks = [_make_chunk(i, 0.5) for i in range(5)]
        assert _coverage_sufficient(chunks)


class TestMergeChunks:
    """Verify _merge_chunks dedup and budget logic."""

    def test_deduplicates_by_chunk_id(self):
        existing = [_make_chunk(1), _make_chunk(2)]
        new = [_make_chunk(2), _make_chunk(3)]
        merged = _merge_chunks(existing, new, budget=10)
        assert [c.chunk_id for c in merged] == [1, 2, 3]

    def test_respects_budget(self):
        existing = [_make_chunk(1), _make_chunk(2)]
        new = [_make_chunk(3), _make_chunk(4)]
        merged = _merge_chunks(existing, new, budget=3)
        assert len(merged) == 3
        assert [c.chunk_id for c in merged] == [1, 2, 3]


class TestExecuteMultiPass:
    """Verify execute_evidence_plan follow-up loops (AR2.2)."""

    @patch("domain.chat.retrieval_context.workspace_has_no_chunks", return_value=False)
    @patch("domain.chat.retrieval_context.apply_concept_bias", side_effect=lambda s, **kw: kw["chunks"])
    @patch("domain.chat.retrieval_context.retrieve_ranked_chunks")
    def test_follow_up_pass_on_low_coverage(
        self, mock_retrieve, mock_bias, mock_no_chunks
    ):
        """When first pass has low coverage and a subquery exists, a second pass runs."""
        # Pass 1: only 2 low-score chunks (below coverage threshold)
        pass1 = [_make_chunk(1, 0.2), _make_chunk(2, 0.2)]
        # Pass 2: concept-name subquery returns additional chunks
        pass2 = [_make_chunk(3, 0.5), _make_chunk(4, 0.5)]
        mock_retrieve.side_effect = [pass1, pass2]

        plan = build_evidence_plan(
            base_query="how does it work?",
            workspace_id=1,
            needs_retrieval=True,
            top_k=20,
            concept_id=7,
            concept_name="Photosynthesis",
        )

        on_pass = MagicMock()
        result_plan, chunks = execute_evidence_plan(
            MagicMock(),
            plan=plan,
            settings=MagicMock(),
            on_pass=on_pass,
        )

        assert result_plan.retrieval_passes_used == 2
        assert len(chunks) == 4
        assert on_pass.call_count == 2
        on_pass.assert_has_calls([
            call(1, "how does it work?"),
            call(2, "Photosynthesis"),
        ])

    @patch("domain.chat.retrieval_context.workspace_has_no_chunks", return_value=False)
    @patch("domain.chat.retrieval_context.apply_concept_bias", side_effect=lambda s, **kw: kw["chunks"])
    @patch("domain.chat.retrieval_context.retrieve_ranked_chunks")
    def test_skip_follow_up_when_coverage_sufficient(
        self, mock_retrieve, mock_bias, mock_no_chunks
    ):
        """When first pass has good coverage, no follow-up is executed."""
        pass1 = [_make_chunk(i, 0.6) for i in range(5)]
        mock_retrieve.return_value = pass1

        plan = build_evidence_plan(
            base_query="explain details",
            workspace_id=1,
            needs_retrieval=True,
            concept_name="Photosynthesis",
        )

        result_plan, chunks = execute_evidence_plan(
            MagicMock(),
            plan=plan,
            settings=MagicMock(),
        )

        assert result_plan.retrieval_passes_used == 1
        assert result_plan.stop_reason == "coverage_sufficient"
        assert mock_retrieve.call_count == 1

    @patch("domain.chat.retrieval_context.workspace_has_no_chunks", return_value=False)
    @patch("domain.chat.retrieval_context.apply_concept_bias", side_effect=lambda s, **kw: kw["chunks"])
    @patch("domain.chat.retrieval_context.retrieve_ranked_chunks")
    def test_max_passes_reached(
        self, mock_retrieve, mock_bias, mock_no_chunks
    ):
        """Planner stops at max_retrieval_passes even if coverage is low."""
        mock_retrieve.return_value = [_make_chunk(1, 0.1)]

        plan = build_evidence_plan(
            base_query="q",
            workspace_id=1,
            needs_retrieval=True,
            concept_name="SomeConcept",
            max_retrieval_passes=1,
        )

        result_plan, _ = execute_evidence_plan(
            MagicMock(),
            plan=plan,
            settings=MagicMock(),
        )

        assert result_plan.retrieval_passes_used == 1
        assert result_plan.stop_reason == "max_passes_reached"

    @patch("domain.chat.retrieval_context.workspace_has_no_chunks", return_value=False)
    @patch("domain.chat.retrieval_context.apply_concept_bias", side_effect=lambda s, **kw: kw["chunks"])
    @patch("domain.chat.retrieval_context.retrieve_ranked_chunks")
    def test_no_subqueries_single_pass(
        self, mock_retrieve, mock_bias, mock_no_chunks
    ):
        """Without subqueries, only one pass runs regardless of coverage."""
        mock_retrieve.return_value = [_make_chunk(1, 0.1)]

        plan = build_evidence_plan(
            base_query="hello",
            workspace_id=1,
            needs_retrieval=True,
        )
        assert plan.subqueries == []

        result_plan, _ = execute_evidence_plan(
            MagicMock(),
            plan=plan,
            settings=MagicMock(),
        )

        assert result_plan.retrieval_passes_used == 1
        assert mock_retrieve.call_count == 1


class TestGraphExpansion:
    """Verify graph-neighbor expansion (AR2.3)."""

    @patch("domain.retrieval.evidence_planner._expand_graph_neighbors")
    def test_graph_neighbors_become_subqueries(self, mock_expand):
        mock_expand.return_value = ["Chloroplast", "Light Reactions"]
        mock_session = MagicMock()

        plan = build_evidence_plan(
            base_query="how does it work?",
            workspace_id=1,
            needs_retrieval=True,
            concept_id=7,
            concept_name="Photosynthesis",
            session=mock_session,
        )

        assert plan.expand_graph_neighbors
        assert plan.graph_hop_budget > 0
        assert "Photosynthesis" in plan.subqueries
        assert "Chloroplast" in plan.subqueries
        assert "Light Reactions" in plan.subqueries

    @patch("domain.retrieval.evidence_planner._expand_graph_neighbors")
    def test_no_graph_expansion_without_concept(self, mock_expand):
        plan = build_evidence_plan(
            base_query="hello",
            workspace_id=1,
            needs_retrieval=True,
            session=MagicMock(),
        )
        assert not plan.expand_graph_neighbors
        mock_expand.assert_not_called()

    @patch("domain.retrieval.evidence_planner._expand_graph_neighbors")
    def test_no_graph_expansion_without_session(self, mock_expand):
        plan = build_evidence_plan(
            base_query="hello",
            workspace_id=1,
            needs_retrieval=True,
            concept_id=7,
        )
        assert not plan.expand_graph_neighbors
        mock_expand.assert_not_called()

    def test_expand_graph_neighbors_returns_names(self):
        mock_session = MagicMock()
        with patch("domain.graph.explore.get_bounded_subgraph") as mock_subgraph:
            mock_subgraph.return_value = {
                "nodes": [
                    {"concept_id": 7, "canonical_name": "Root"},
                    {"concept_id": 8, "canonical_name": "Neighbor1"},
                    {"concept_id": 9, "canonical_name": "Neighbor2"},
                    {"concept_id": 10, "canonical_name": "Neighbor3"},
                ],
                "edges": [],
            }
            names = _expand_graph_neighbors(
                mock_session,
                workspace_id=1,
                concept_id=7,
            )
        # Root excluded, max 2 neighbors
        assert names == ["Neighbor1", "Neighbor2"]

    def test_expand_graph_neighbors_handles_no_session(self):
        names = _expand_graph_neighbors(
            object(),  # no execute attribute
            workspace_id=1,
            concept_id=7,
        )
        assert names == []

    def test_document_summaries_flag_active(self):
        plan = build_evidence_plan(
            base_query="q",
            workspace_id=1,
            needs_retrieval=True,
        )
        assert plan.expand_document_summaries


class TestSourceAccounting:
    """Verify retrieved-vs-used source accounting fields (AR2.4)."""

    def test_generation_trace_has_accounting_fields(self):
        from core.schemas.assistant import GenerationTrace

        trace = GenerationTrace(
            evidence_plan_retrieved_count=10,
            evidence_plan_used_count=3,
        )
        assert trace.evidence_plan_retrieved_count == 10
        assert trace.evidence_plan_used_count == 3

    def test_generation_trace_defaults_none(self):
        from core.schemas.assistant import GenerationTrace

        trace = GenerationTrace()
        assert trace.evidence_plan_retrieved_count is None
        assert trace.evidence_plan_used_count is None

    def test_retrieved_count_matches_plan(self):
        """retrieved_chunk_count on EvidencePlan maps to retrieved_count in trace."""
        plan = build_evidence_plan(
            base_query="test",
            workspace_id=1,
            needs_retrieval=True,
        )
        assert plan.retrieved_chunk_count == 0

        from domain.retrieval.types import RankedChunk

        chunks = [
            RankedChunk(
                workspace_id=1, document_id=1, chunk_id=i,
                chunk_index=0, text=f"chunk {i}", score=0.5,
                retrieval_method="vector",
            )
            for i in range(5)
        ]
        updated = plan.with_results(
            stop_reason="coverage_sufficient",
            retrieved_chunk_count=5,
        )
        assert updated.retrieved_chunk_count == 5


class TestProvenanceExpansion:
    """Verify provenance-linked expansion stage (AR2.5)."""

    @patch("domain.retrieval.evidence_planner._discover_provenance_chunk_ids")
    @patch("domain.retrieval.evidence_planner._expand_graph_neighbors")
    def test_provenance_ids_populated_in_plan(self, mock_expand, mock_prov):
        mock_expand.return_value = []
        mock_prov.return_value = [100, 101, 102]
        session = MagicMock()

        plan = build_evidence_plan(
            base_query="explain mitosis",
            workspace_id=1,
            needs_retrieval=True,
            concept_id=5,
            session=session,
        )
        assert plan.provenance_linked_chunk_ids == [100, 101, 102]

    @patch("domain.retrieval.evidence_planner._discover_provenance_chunk_ids")
    @patch("domain.retrieval.evidence_planner._expand_graph_neighbors")
    def test_no_provenance_without_concept(self, mock_expand, mock_prov):
        plan = build_evidence_plan(
            base_query="hello",
            workspace_id=1,
            needs_retrieval=True,
            session=MagicMock(),
        )
        assert plan.provenance_linked_chunk_ids == []
        mock_prov.assert_not_called()

    @patch("domain.chat.retrieval_context.retrieve_chunks_by_ids")
    @patch("domain.chat.retrieval_context.workspace_has_no_chunks", return_value=False)
    @patch("domain.chat.retrieval_context.apply_concept_bias", side_effect=lambda s, **kw: kw["chunks"])
    @patch("domain.chat.retrieval_context.retrieve_ranked_chunks")
    def test_provenance_expansion_adds_missing_chunks(
        self, mock_retrieve, mock_bias, mock_no_chunks, mock_by_ids
    ):
        """Provenance-linked chunks not in initial results get merged in."""
        pass1 = [_make_chunk(1, 0.5), _make_chunk(2, 0.5), _make_chunk(3, 0.5)]
        mock_retrieve.return_value = pass1
        # Provenance returns chunk 4 and 5 (not in pass1)
        mock_by_ids.return_value = [_make_chunk(4, 0.3), _make_chunk(5, 0.3)]

        plan = EvidencePlan(
            base_query="q",
            workspace_id=1,
            candidate_concept_ids=[7],
            provenance_linked_chunk_ids=[2, 4, 5],  # 2 already in results
            retrieval_budget=20,
        )

        result_plan, chunks = execute_evidence_plan(
            MagicMock(), plan=plan, settings=MagicMock()
        )
        assert result_plan.provenance_chunks_added == 2
        assert len(chunks) == 5
        chunk_ids = {c.chunk_id for c in chunks}
        assert {1, 2, 3, 4, 5} == chunk_ids
        # Only missing IDs (4, 5) requested
        mock_by_ids.assert_called_once()
        call_ids = mock_by_ids.call_args.kwargs["chunk_ids"]
        assert call_ids == [4, 5]

    @patch("domain.chat.retrieval_context.workspace_has_no_chunks", return_value=False)
    @patch("domain.chat.retrieval_context.apply_concept_bias", side_effect=lambda s, **kw: kw["chunks"])
    @patch("domain.chat.retrieval_context.retrieve_ranked_chunks")
    def test_provenance_skipped_when_no_ids(
        self, mock_retrieve, mock_bias, mock_no_chunks
    ):
        """No provenance expansion when provenance_linked_chunk_ids is empty."""
        mock_retrieve.return_value = [_make_chunk(1, 0.5)]

        plan = EvidencePlan(
            base_query="q",
            workspace_id=1,
            provenance_linked_chunk_ids=[],
            retrieval_budget=20,
        )

        result_plan, chunks = execute_evidence_plan(
            MagicMock(), plan=plan, settings=MagicMock()
        )
        assert result_plan.provenance_chunks_added == 0
        assert len(chunks) == 1

    @patch("domain.chat.retrieval_context.retrieve_chunks_by_ids")
    @patch("domain.chat.retrieval_context.workspace_has_no_chunks", return_value=False)
    @patch("domain.chat.retrieval_context.apply_concept_bias", side_effect=lambda s, **kw: kw["chunks"])
    @patch("domain.chat.retrieval_context.retrieve_ranked_chunks")
    def test_provenance_respects_budget(
        self, mock_retrieve, mock_bias, mock_no_chunks, mock_by_ids
    ):
        """Provenance expansion stops when budget is reached."""
        pass1 = [_make_chunk(i, 0.5) for i in range(18)]
        mock_retrieve.return_value = pass1
        mock_by_ids.return_value = [_make_chunk(100 + i, 0.3) for i in range(5)]

        plan = EvidencePlan(
            base_query="q",
            workspace_id=1,
            provenance_linked_chunk_ids=[100, 101, 102, 103, 104],
            retrieval_budget=20,
        )

        result_plan, chunks = execute_evidence_plan(
            MagicMock(), plan=plan, settings=MagicMock()
        )
        assert len(chunks) == 20  # budget cap
        assert result_plan.provenance_chunks_added == 2


class TestDocumentSummaryExpansion:
    """Verify document-summary expansion stage (AR2.5)."""

    @patch("domain.chat.retrieval_context.workspace_has_no_chunks", return_value=False)
    @patch("domain.chat.retrieval_context.retrieve_ranked_chunks")
    def test_expanded_document_ids_populated(self, mock_retrieve, mock_no_chunks):
        """When expand_document_summaries=True, doc IDs are gathered."""
        chunks = [
            RankedChunk(
                workspace_id=1, document_id=doc_id, chunk_id=i,
                chunk_index=0, text=f"t{i}", score=0.5, retrieval_method="hybrid",
            )
            for i, doc_id in enumerate([10, 20, 10, 30])
        ]
        mock_retrieve.return_value = chunks

        plan = EvidencePlan(
            base_query="q",
            workspace_id=1,
            expand_document_summaries=True,
            retrieval_budget=20,
        )

        result_plan, _ = execute_evidence_plan(
            MagicMock(), plan=plan, settings=MagicMock()
        )
        assert result_plan.expanded_document_ids == [10, 20, 30]

    @patch("domain.chat.retrieval_context.workspace_has_no_chunks", return_value=False)
    @patch("domain.chat.retrieval_context.retrieve_ranked_chunks")
    def test_no_doc_ids_when_flag_false(self, mock_retrieve, mock_no_chunks):
        """When expand_document_summaries=False, no doc IDs gathered."""
        mock_retrieve.return_value = [_make_chunk(1)]

        plan = EvidencePlan(
            base_query="q",
            workspace_id=1,
            expand_document_summaries=False,
            retrieval_budget=20,
        )

        result_plan, _ = execute_evidence_plan(
            MagicMock(), plan=plan, settings=MagicMock()
        )
        assert result_plan.expanded_document_ids == []

    @patch("domain.chat.retrieval_context.workspace_has_no_chunks", return_value=False)
    @patch("domain.chat.retrieval_context.retrieve_ranked_chunks")
    def test_doc_ids_capped_at_five(self, mock_retrieve, mock_no_chunks):
        """Document ID list is capped at 5 unique values."""
        chunks = [
            RankedChunk(
                workspace_id=1, document_id=doc_id, chunk_id=i,
                chunk_index=0, text=f"t{i}", score=0.5, retrieval_method="hybrid",
            )
            for i, doc_id in enumerate([1, 2, 3, 4, 5, 6, 7])
        ]
        mock_retrieve.return_value = chunks

        plan = EvidencePlan(
            base_query="q",
            workspace_id=1,
            expand_document_summaries=True,
            retrieval_budget=20,
        )

        result_plan, _ = execute_evidence_plan(
            MagicMock(), plan=plan, settings=MagicMock()
        )
        assert len(result_plan.expanded_document_ids) == 5

    def test_trace_fields_for_expansion(self):
        """GenerationTrace includes new provenance/doc-summary trace fields."""
        from core.schemas.assistant import GenerationTrace

        trace = GenerationTrace(
            evidence_plan_provenance_chunks=3,
            evidence_plan_doc_summary_ids=2,
        )
        assert trace.evidence_plan_provenance_chunks == 3
        assert trace.evidence_plan_doc_summary_ids == 2

    def test_with_results_carries_new_fields(self):
        """with_results() properly carries provenance and doc-summary fields."""
        plan = EvidencePlan(
            base_query="q",
            workspace_id=1,
            retrieval_budget=20,
        )
        updated = plan.with_results(
            stop_reason="coverage_sufficient",
            retrieved_chunk_count=10,
            provenance_chunks_added=3,
            expanded_document_ids=[10, 20],
        )
        assert updated.provenance_chunks_added == 3
        assert updated.expanded_document_ids == [10, 20]
