import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "@/lib/api/client";
import type {
  ConceptSwitchSuggestion,
  GraphConceptSummary,
  GraphSubgraphResponse,
  GroundingMode,
  OnboardingStatusResponse,
} from "@/lib/api/types";
import { useChatSession } from "@/lib/tutor/chat-session-context";
import { useRequireAuth } from "@/lib/auth";
import { useLevelUpFlow } from "./use-level-up-flow";
import { useTutorMessages } from "./use-tutor-messages";
import { errorText } from "../types";

export function useTutorPage() {
  const { user, isLoading: authLoading, activeWorkspaceId } = useRequireAuth();
  const wsId = activeWorkspaceId ?? undefined;
  const { activeSessionId, startNewSession, refreshSessions } = useChatSession();

  const [grounding_mode, setGroundingMode] = useState<GroundingMode>("hybrid");

  // Concept state
  const [concepts, setConcepts] = useState<GraphConceptSummary[]>([]);
  const [conceptsLoading, setConceptsLoading] = useState(false);
  const [conceptsError, setConceptsError] = useState<string | null>(null);
  const [currentConcept, setCurrentConcept] = useState<GraphConceptSummary | null>(null);
  const [subgraph, setSubgraph] = useState<GraphSubgraphResponse | null>(null);
  const [graphViewConceptId, setGraphViewConceptId] = useState<number | null>(null);

  // Concept switch state
  const [suggestedConceptId, setSuggestedConceptId] = useState<number | null>(null);
  const [switchSuggestion, setSwitchSuggestion] = useState<ConceptSwitchSuggestion | null>(null);
  const [switchDecision, setSwitchDecision] = useState<"accept" | "reject" | null>(null);
  const switchDecisionRef = useRef<"accept" | "reject" | null>(null);

  // Drawer state
  const [showGraph, setShowGraph] = useState(false);
  const [showQuiz, setShowQuiz] = useState(false);
  const [closingDrawer, setClosingDrawer] = useState<"graph" | "quiz" | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const tutorResetViewRef = useRef<(() => void) | null>(null);

  // Onboarding
  const [onboarding, setOnboarding] = useState<OnboardingStatusResponse | null>(null);

  async function ensureSession(): Promise<string | null> {
    if (!wsId) return null;
    if (activeSessionId) return activeSessionId;
    return await startNewSession();
  }

  // Sub-hooks
  const { levelUpState, dispatchLevelUp, startLevelUp, submitLevelUp } = useLevelUpFlow(
    wsId,
    currentConcept,
    ensureSession,
  );

  const {
    messages,
    chatLoading,
    chatPhase,
    chatError,
    streamFallback,
    activitySteps,
    query,
    setQuery,
    onSubmitChat,
  } = useTutorMessages({
    wsId,
    activeSessionId,
    currentConcept,
    concepts,
    suggestedConceptId,
    switchDecisionRef,
    grounding_mode,
    refreshSessions,
    setCurrentConcept,
    setSwitchSuggestion,
    setSuggestedConceptId,
    setSwitchDecision,
  });

  // Load concepts
  const loadConcepts = useCallback(async () => {
    if (!wsId) return;
    setConceptsLoading(true);
    setConceptsError(null);
    try {
      const payload = await apiClient.listConcepts(wsId, { limit: 120 });
      setConcepts(payload.concepts);
      setCurrentConcept((prev) => {
        if (prev) {
          const matched = payload.concepts.find((item) => item.concept_id === prev.concept_id);
          if (matched) return matched;
        }
        return payload.concepts[0] ?? null;
      });
    } catch (error: unknown) {
      setConceptsError(errorText(error, "Failed to load concepts"));
      setConcepts([]);
      setCurrentConcept(null);
    } finally {
      setConceptsLoading(false);
    }
  }, [wsId]);

  async function loadSubgraph(conceptId: number) {
    if (!wsId) return;
    try {
      const payload = await apiClient.getConceptSubgraph(wsId, conceptId, {
        max_hops: 2,
        max_nodes: 40,
        max_edges: 80,
      });
      const allowedIds = new Set<number>();
      for (const node of payload.nodes) {
        if (
          node.concept_id === conceptId ||
          node.mastery_status === "learned" ||
          node.mastery_status === "learning" ||
          node.hop_distance <= 1
        ) {
          allowedIds.add(node.concept_id);
        }
      }
      const filteredNodes = payload.nodes.filter((n) => allowedIds.has(n.concept_id));
      const filteredEdges = payload.edges.filter(
        (e) => allowedIds.has(e.src_concept_id) && allowedIds.has(e.tgt_concept_id),
      );
      setSubgraph({ ...payload, nodes: filteredNodes, edges: filteredEdges });
    } catch {
      setSubgraph(null);
    }
  }

  function closeDrawer(which: "graph" | "quiz", onDone?: () => void) {
    setClosingDrawer(which);
    if (!onDone) setDrawerOpen(false);
    setTimeout(() => {
      if (which === "graph") setShowGraph(false);
      else setShowQuiz(false);
      setClosingDrawer(null);
      onDone?.();
    }, 320);
  }

  function openDrawer(which: "graph" | "quiz") {
    if (which === "graph") setShowGraph(true);
    else setShowQuiz(true);
    setDrawerOpen(true);
  }

  // Effects
  useEffect(() => {
    void loadConcepts();
  }, [loadConcepts]);

  useEffect(() => {
    if (!wsId) return;
    apiClient.getOnboardingStatus(wsId).then(setOnboarding).catch(() => setOnboarding(null));
  }, [wsId]);

  // Reset level-up when session changes and no active session
  useEffect(() => {
    if (!activeSessionId) {
      dispatchLevelUp({ type: "reset" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId]);

  useEffect(() => {
    if (showGraph && currentConcept) {
      void loadSubgraph(currentConcept.concept_id);
      setGraphViewConceptId(currentConcept.concept_id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showGraph, currentConcept?.concept_id, wsId]);

  return {
    // Auth
    user,
    authLoading,
    wsId,
    // Chat
    messages,
    chatLoading,
    chatPhase,
    chatError,
    streamFallback,
    activitySteps,
    query,
    setQuery,
    onSubmitChat,
    grounding_mode,
    setGroundingMode,
    // Concepts
    concepts,
    conceptsLoading,
    conceptsError,
    currentConcept,
    setCurrentConcept,
    subgraph,
    graphViewConceptId,
    setGraphViewConceptId,
    loadSubgraph,
    tutorResetViewRef,
    // Level-up
    levelUpState,
    dispatchLevelUp,
    startLevelUp,
    submitLevelUp,
    // Concept switch
    suggestedConceptId,
    setSuggestedConceptId,
    switchSuggestion,
    setSwitchSuggestion,
    switchDecision,
    setSwitchDecision,
    switchDecisionRef,
    // Drawers
    showGraph,
    showQuiz,
    drawerOpen,
    closingDrawer,
    openDrawer,
    closeDrawer,
    // Onboarding
    onboarding,
  };
}
