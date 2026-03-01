import { useReducer, useEffect, useState, useCallback } from "react";
import { ApiError, apiClient } from "@/lib/api/client";
import { graphReducer, initialGraphState } from "@/lib/graph/graph-state";
import {
  practiceReducer,
  initialPracticeState,
  toPracticeAnswers,
} from "@/lib/practice/practice-state";
import { useConceptActivity } from "@/lib/practice/use-concept-activity";
import { useRequireAuth } from "@/lib/auth";
import { useDebounce } from "@/lib/hooks/use-debounce";
import type {
  LuckyMode,
  StatefulFlashcard,
  FlashcardSelfRating,
  GraphSubgraphNode,
  GraphSubgraphEdge,
} from "@/lib/api/types";

export function useGraphPage() {
  const auth = useRequireAuth();
  const wsId = auth.activeWorkspaceId ?? "";
  const [state, dispatch] = useReducer(graphReducer, initialGraphState);
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 300);
  const [luckyLoading, setLuckyLoading] = useState(false);

  // Practice state
  const [practiceState, dispatchPractice] = useReducer(practiceReducer, initialPracticeState);
  const [practiceMode, setPracticeMode] = useState<"none" | "flashcards" | "quiz">("none");

  // Stateful flashcards state
  const [statefulCards, setStatefulCards] = useState<StatefulFlashcard[]>([]);
  const [statefulConceptName, setStatefulConceptName] = useState("");
  const [statefulLoading, setStatefulLoading] = useState(false);
  const [statefulError, setStatefulError] = useState<string | null>(null);
  const [ratingInFlight, setRatingInFlight] = useState(false);

  // Practice history for selected concept
  const selectedConceptId = state.selectedDetail?.concept.concept_id ?? null;
  const conceptActivity = useConceptActivity(wsId || undefined, selectedConceptId ?? undefined);

  // Full graph state
  const [fullGraph, setFullGraph] = useState<{
    nodes: GraphSubgraphNode[];
    edges: GraphSubgraphEdge[];
    is_truncated?: boolean;
    total_concept_count?: number;
  } | null>(null);

  // Graph controls
  const [maxNodes, setMaxNodes] = useState(100);
  const [maxEdges, setMaxEdges] = useState(300);
  const [maxHops, setMaxHops] = useState(2);
  const [graphSearch, setGraphSearch] = useState("");
  const debouncedGraphSearch = useDebounce(graphSearch, 200);
  const [focusNodeId, setFocusNodeId] = useState<number | null>(null);
  const [resetView, setResetView] = useState<(() => void) | null>(null);

  // Tier filter state
  const [filteredTiers, setFilteredTiers] = useState<Set<string>>(new Set());
  const toggleTierFilter = useCallback((tier: string) => {
    setFilteredTiers(prev => {
      const next = new Set(prev);
      if (next.has(tier)) next.delete(tier); else next.add(tier);
      return next;
    });
  }, []);
  const clearTierFilter = useCallback(() => setFilteredTiers(new Set()), []);

  const handleResetViewReady = useCallback((fn: () => void) => {
    setResetView(() => fn);
  }, []);

  useEffect(() => {
    if (!wsId) return;
    dispatch({ type: "list_start" });
    apiClient
      .listConcepts(wsId, { q: debouncedQuery || undefined, limit: 50 })
      .then((r) => dispatch({ type: "list_success", concepts: r.concepts }))
      .catch((e) =>
        dispatch({
          type: "list_error",
          error: e instanceof ApiError ? e.message : "Failed to load concepts",
        }),
      );
  }, [debouncedQuery, wsId]);

  useEffect(() => {
    if (!wsId || debouncedQuery.trim().length > 0 || state.selectedDetail) return;
    apiClient
      .getFullGraph(wsId, { max_nodes: maxNodes, max_edges: maxEdges })
      .then((res) => setFullGraph(res))
      .catch((e) => console.error("Failed to load full graph overview", e));
  }, [wsId, debouncedQuery, state.selectedDetail, maxNodes, maxEdges]);

  const selectConcept = useCallback(
    (conceptId: number) => {
      dispatch({ type: "detail_start" });
      dispatchPractice({ type: "reset" });
      setPracticeMode("none");
      setStatefulCards([]);
      setStatefulError(null);
      Promise.all([
        apiClient.getConceptDetail(wsId, conceptId),
        apiClient.getConceptSubgraph(wsId, conceptId, {
          max_hops: maxHops,
          max_nodes: 40,
          max_edges: 80,
        }),
      ])
        .then(([detail, subgraph]) =>
          dispatch({ type: "detail_success", detail, subgraph }),
        )
        .catch((e) =>
          dispatch({
            type: "detail_error",
            error: e instanceof ApiError ? e.message : "Failed to load detail",
          }),
        );
    },
    [wsId, maxHops],
  );

  const lucky = useCallback(
    (mode: LuckyMode) => {
      const conceptId = state.selectedDetail?.concept.concept_id;
      if (!conceptId) return;
      setLuckyLoading(true);
      apiClient
        .getLuckyPick(wsId, { concept_id: conceptId, mode, k_hops: 2 })
        .then((pick) => dispatch({ type: "lucky_success", pick }))
        .catch((e) =>
          dispatch({
            type: "lucky_error",
            error: e instanceof ApiError ? e.message : "Lucky pick failed",
          }),
        )
        .finally(() => setLuckyLoading(false));
    },
    [state.selectedDetail, wsId],
  );

  const loadStatefulFlashcards = useCallback(() => {
    const conceptId = state.selectedDetail?.concept.concept_id;
    if (!conceptId) return;
    setPracticeMode("flashcards");
    setStatefulLoading(true);
    setStatefulError(null);
    apiClient
      .generateStatefulFlashcards(wsId, { concept_id: conceptId })
      .then((res) => {
        setStatefulCards(res.flashcards);
        setStatefulConceptName(res.concept_name);
      })
      .catch((e) =>
        setStatefulError(
          e instanceof ApiError ? e.message : "Failed to generate flashcards",
        ),
      )
      .finally(() => setStatefulLoading(false));
  }, [state.selectedDetail, wsId]);

  const handleRate = useCallback(
    (flashcardId: string, rating: FlashcardSelfRating) => {
      setRatingInFlight(true);
      apiClient
        .rateFlashcard(wsId, { flashcard_id: flashcardId, self_rating: rating })
        .then((res) => {
          setStatefulCards((prev) =>
            prev.map((c) =>
              c.flashcard_id === res.flashcard_id
                ? { ...c, self_rating: res.self_rating, passed: res.passed }
                : c,
            ),
          );
        })
        .catch(() => {})
        .finally(() => setRatingInFlight(false));
    },
    [wsId],
  );

  const loadQuiz = useCallback(() => {
    const conceptId = state.selectedDetail?.concept.concept_id;
    if (!conceptId) return;
    setPracticeMode("quiz");
    dispatchPractice({ type: "quiz_start" });
    apiClient
      .createPracticeQuiz(wsId, { concept_id: conceptId })
      .then((quiz) => dispatchPractice({ type: "quiz_success", quiz }))
      .catch((e) =>
        dispatchPractice({
          type: "quiz_error",
          error: e instanceof ApiError ? e.message : "Failed to create practice quiz",
        }),
      );
  }, [state.selectedDetail, wsId]);

  const submitQuiz = useCallback(() => {
    if (!practiceState.quiz) return;
    dispatchPractice({ type: "submit_start" });
    apiClient
      .submitPracticeQuiz(wsId, practiceState.quiz.quiz_id, {
        answers: toPracticeAnswers(practiceState.quiz.items, practiceState.answers),
      })
      .then((result) => dispatchPractice({ type: "submit_success", result }))
      .catch((e) =>
        dispatchPractice({
          type: "submit_error",
          error: e instanceof ApiError ? e.message : "Failed to submit practice quiz",
        }),
      );
  }, [practiceState.quiz, practiceState.answers, wsId]);

  const handleGraphSelect = useCallback(
    (id: number) => {
      selectConcept(id);
      setFocusNodeId(id);
    },
    [selectConcept],
  );

  const handleGraphBgClick = useCallback(() => {
    dispatch({ type: "clear_detail" });
    setFocusNodeId(null);
  }, []);

  const handleNextQuiz = useCallback(() => {
    if (!wsId || !state.selectedDetail) return;
    dispatchPractice({ type: "quiz_start" });
    apiClient
      .createPracticeQuiz(wsId, { concept_id: state.selectedDetail.concept.concept_id })
      .then((quiz) => dispatchPractice({ type: "quiz_success", quiz }))
      .catch((e) =>
        dispatchPractice({
          type: "quiz_error",
          error: e instanceof ApiError ? e.message : "Failed to create practice quiz",
        }),
      );
  }, [wsId, state.selectedDetail]);

  return {
    auth,
    state,
    dispatch,
    query,
    setQuery,
    debouncedQuery,
    luckyLoading,
    practiceState,
    dispatchPractice,
    practiceMode,
    setPracticeMode,
    statefulCards,
    setStatefulCards,
    statefulConceptName,
    statefulLoading,
    statefulError,
    ratingInFlight,
    fullGraph,
    maxNodes,
    setMaxNodes,
    maxEdges,
    setMaxEdges,
    maxHops,
    setMaxHops,
    graphSearch,
    setGraphSearch,
    debouncedGraphSearch,
    focusNodeId,
    setFocusNodeId,
    resetView,
    handleResetViewReady,
    selectConcept,
    lucky,
    loadStatefulFlashcards,
    handleRate,
    loadQuiz,
    submitQuiz,
    handleGraphSelect,
    handleGraphBgClick,
    handleNextQuiz,
    conceptActivity,
    filteredTiers,
    toggleTierFilter,
    clearTierFilter,
  };
}
