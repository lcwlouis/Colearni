import type {
  GraphConceptSummary,
  GraphConceptDetailResponse,
  GraphSubgraphResponse,
  GraphLuckyResponse,
} from "@/lib/api/types";

export type GraphPhase =
  | "idle"
  | "loading_list"
  | "list_ready"
  | "loading_detail"
  | "detail_ready"
  | "error";

export interface GraphState {
  phase: GraphPhase;
  concepts: GraphConceptSummary[];
  selectedDetail: GraphConceptDetailResponse | null;
  subgraph: GraphSubgraphResponse | null;
  luckyPick: GraphLuckyResponse | null;
  error: string | null;
}

export type GraphAction =
  | { type: "list_start" }
  | { type: "list_success"; concepts: GraphConceptSummary[] }
  | { type: "list_error"; error: string }
  | { type: "detail_start" }
  | { type: "detail_success"; detail: GraphConceptDetailResponse; subgraph: GraphSubgraphResponse }
  | { type: "detail_error"; error: string }
  | { type: "lucky_success"; pick: GraphLuckyResponse }
  | { type: "lucky_error"; error: string }
  | { type: "clear_lucky" }
  | { type: "clear_detail" }
  | { type: "reset" };

export const initialGraphState: GraphState = {
  phase: "idle",
  concepts: [],
  selectedDetail: null,
  subgraph: null,
  luckyPick: null,
  error: null,
};

export function graphReducer(state: GraphState, action: GraphAction): GraphState {
  if (action.type === "list_start") {
    return { ...state, phase: "loading_list", concepts: [], error: null };
  }
  if (action.type === "list_success") {
    return { ...state, phase: "list_ready", concepts: action.concepts, error: null };
  }
  if (action.type === "list_error") {
    return { ...state, phase: "error", error: action.error };
  }
  if (action.type === "detail_start") {
    return { ...state, phase: "loading_detail", selectedDetail: null, subgraph: null, luckyPick: null, error: null };
  }
  if (action.type === "detail_success") {
    return { ...state, phase: "detail_ready", selectedDetail: action.detail, subgraph: action.subgraph, error: null };
  }
  if (action.type === "detail_error") {
    return { ...state, phase: "error", error: action.error };
  }
  if (action.type === "lucky_success") {
    return { ...state, luckyPick: action.pick };
  }
  if (action.type === "lucky_error") {
    return { ...state, error: action.error };
  }
  if (action.type === "clear_lucky") {
    return { ...state, luckyPick: null };
  }
  if (action.type === "clear_detail") {
    return { ...state, phase: "list_ready", selectedDetail: null, subgraph: null, luckyPick: null, error: null };
  }
  if (action.type === "reset") {
    return initialGraphState;
  }
  return state;
}
