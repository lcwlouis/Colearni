import { describe, expect, it } from "vitest";
import { graphReducer, initialGraphState } from "./graph-state";
import type { GraphConceptSummary, GraphConceptDetailResponse, GraphSubgraphResponse, GraphLuckyResponse } from "@/lib/api/types";

const concept: GraphConceptSummary = { concept_id: 1, canonical_name: "Linear Map", description: "Preserves operations.", degree: 3, mastery_status: null, mastery_score: null };
const detail: GraphConceptDetailResponse = { workspace_id: 1, concept: { concept_id: 1, canonical_name: "Linear Map", description: "Preserves operations.", aliases: ["Linear Transformation"], degree: 3 } };
const subgraph: GraphSubgraphResponse = { workspace_id: 1, root_concept_id: 1, max_hops: 1, nodes: [{ concept_id: 1, canonical_name: "Linear Map", description: "x", hop_distance: 0, mastery_status: null, mastery_score: null }, { concept_id: 2, canonical_name: "Kernel", description: "y", hop_distance: 1, mastery_status: null, mastery_score: null }], edges: [] };
const luckyPick: GraphLuckyResponse = { workspace_id: 1, seed_concept_id: 1, mode: "adjacent", pick: { concept_id: 2, canonical_name: "Kernel", description: "Vectors mapped to zero.", hop_distance: 1 } };

describe("graphReducer", () => {
    it("starts in idle phase", () => {
        expect(initialGraphState.phase).toBe("idle");
    });

    it("list_start sets loading_list", () => {
        const s = graphReducer(initialGraphState, { type: "list_start" });
        expect(s.phase).toBe("loading_list");
        expect(s.concepts).toEqual([]);
    });

    it("list_success populates concepts", () => {
        const s = graphReducer(initialGraphState, { type: "list_success", concepts: [concept] });
        expect(s.phase).toBe("list_ready");
        expect(s.concepts).toHaveLength(1);
        expect(s.concepts[0].canonical_name).toBe("Linear Map");
    });

    it("list_error sets error", () => {
        const s = graphReducer(initialGraphState, { type: "list_error", error: "fail" });
        expect(s.phase).toBe("error");
        expect(s.error).toBe("fail");
    });

    it("detail_start clears previous detail but preserves subgraph", () => {
        const prev = { ...initialGraphState, selectedDetail: detail, subgraph };
        const s = graphReducer(prev, { type: "detail_start" });
        expect(s.phase).toBe("loading_detail");
        expect(s.selectedDetail).toBeNull();
        expect(s.subgraph).not.toBeNull();
        expect(s.luckyPick).toBeNull();
    });

    it("detail_success sets detail and subgraph", () => {
        const s = graphReducer(initialGraphState, { type: "detail_success", detail, subgraph });
        expect(s.phase).toBe("detail_ready");
        expect(s.selectedDetail?.concept.canonical_name).toBe("Linear Map");
        expect(s.subgraph?.nodes).toHaveLength(2);
    });

    it("lucky_success sets pick", () => {
        const s = graphReducer(initialGraphState, { type: "lucky_success", pick: luckyPick });
        expect(s.luckyPick?.mode).toBe("adjacent");
    });

    it("lucky_error sets error without changing phase", () => {
        const prev = { ...initialGraphState, phase: "detail_ready" as const };
        const s = graphReducer(prev, { type: "lucky_error", error: "no candidates" });
        expect(s.error).toBe("no candidates");
        expect(s.phase).toBe("detail_ready");
    });

    it("clear_lucky clears pick", () => {
        const prev = { ...initialGraphState, luckyPick };
        const s = graphReducer(prev, { type: "clear_lucky" });
        expect(s.luckyPick).toBeNull();
    });

    it("reset returns initial state", () => {
        const prev = { ...initialGraphState, phase: "detail_ready" as const, selectedDetail: detail };
        expect(graphReducer(prev, { type: "reset" })).toEqual(initialGraphState);
    });
});
