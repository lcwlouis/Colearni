import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiClient } from "@/lib/api/client";
import type {
  ConceptSwitchSuggestion,
  GraphConceptSummary,
  GraphSubgraphResponse,
  GroundingMode,
  HierarchyNode,
  OnboardingStatusResponse,
} from "@/lib/api/types";
import { useChatSession } from "@/lib/tutor/chat-session-context";
import { useRequireAuth } from "@/lib/auth";
import { useLevelUpFlow } from "./use-level-up-flow";
import { useTutorMessages } from "./use-tutor-messages";
import { useConceptActivity } from "@/lib/practice/use-concept-activity";
import { errorText } from "../types";
import type { SlideOverTab } from "../components/tutor-slide-over";

export function useTutorPage() {
  const { user, isLoading: authLoading, activeWorkspaceId } = useRequireAuth();
  const wsId = activeWorkspaceId ?? undefined;
  const { activeSessionId, setActiveSessionId, startNewSession, refreshSessions, sessions } = useChatSession();
  const searchParams = useSearchParams();
  const topicParam = searchParams.get("topic");
  const sessionParam = searchParams.get("session");

  const [grounding_mode, setGroundingMode] = useState<GroundingMode>("hybrid");
  const [tutorProtocol, setTutorProtocol] = useState(false);

  // Derive session title from active session
  const activeSession = sessions.find((s) => s.public_id === activeSessionId);
  const sessionTitle = activeSession?.title ?? null;

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

  // Hierarchy breadcrumb state
  const [hierarchyPath, setHierarchyPath] = useState<HierarchyNode[]>([]);

  // Slide-over state (unified drawer)
  const [showSlideOver, setShowSlideOver] = useState(false);
  const [slideOverTab, setSlideOverTab] = useState<SlideOverTab>("graph");
  const [closingDrawer, setClosingDrawer] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const tutorResetViewRef = useRef<(() => void) | null>(null);

  // Onboarding
  const [onboarding, setOnboarding] = useState<OnboardingStatusResponse | null>(null);

  // Concept activity for graph drawer
  const activityConceptId = graphViewConceptId ?? currentConcept?.concept_id ?? undefined;
  const conceptActivity = useConceptActivity(wsId, activityConceptId);

  async function ensureSession(): Promise<string | null> {
    if (!wsId) return null;
    if (activeSessionId) return activeSessionId;
    return await startNewSession(currentConcept?.concept_id);
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
    tutorProtocol,
    refreshSessions,
    setCurrentConcept,
    setSwitchSuggestion,
    setSuggestedConceptId,
    setSwitchDecision,
    setHierarchyPath,
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

  function closeDrawer(onDone?: () => void) {
    setClosingDrawer(true);
    if (!onDone) setDrawerOpen(false);
    setTimeout(() => {
      setShowSlideOver(false);
      setClosingDrawer(false);
      onDone?.();
    }, 320);
  }

  function openDrawer(which: "graph" | "quiz" | "practice") {
    const tab: SlideOverTab = which === "quiz" ? "level-up" : which === "practice" ? "practice" : "graph";
    setSlideOverTab(tab);
    setShowSlideOver(true);
    setDrawerOpen(true);
  }

  function toggleSidebar() {
    if (showSlideOver) {
      closeDrawer();
    } else {
      setShowSlideOver(true);
      setDrawerOpen(true);
    }
  }

  // Effects
  useEffect(() => {
    void loadConcepts();
  }, [loadConcepts]);

  useEffect(() => {
    if (!wsId) return;
    apiClient.getOnboardingStatus(wsId).then(setOnboarding).catch(() => setOnboarding(null));
  }, [wsId]);

  // Fetch feature flags from backend for Socratic default
  useEffect(() => {
    apiClient.getFeatureFlags()
      .then((flags) => {
        setTutorProtocol(flags.socratic_mode_default);
      })
      .catch(() => { /* keep local default */ });
  }, []);
  const topicConsumedRef = useRef(false);
  const conceptIdParam = searchParams.get("concept_id");
  useEffect(() => {
    if (topicParam && !topicConsumedRef.current) {
      topicConsumedRef.current = true;
      setQuery(`Teach me about ${topicParam}`);

      // Bind session to the concept from the URL
      const cid = conceptIdParam ? Number(conceptIdParam) : null;
      if (cid && concepts.length) {
        const matched = concepts.find((c) => c.concept_id === cid);
        if (matched) setCurrentConcept(matched);
      }
      if (cid) {
        void startNewSession(cid);
      }
    }
  }, [topicParam, conceptIdParam, concepts, setQuery]); // eslint-disable-line react-hooks/exhaustive-deps

  // Navigate to a specific chat session when ?session= param is present
  useEffect(() => {
    if (sessionParam) {
      setActiveSessionId(sessionParam);
    }
  }, [sessionParam, setActiveSessionId]);

  // Reset level-up when session changes and no active session
  useEffect(() => {
    if (!activeSessionId) {
      dispatchLevelUp({ type: "reset" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId]);

  // S1.7: Sync currentConcept from session's bound concept_id
  useEffect(() => {
    if (!activeSession?.concept_id || !concepts.length) return;
    const matched = concepts.find((c) => c.concept_id === activeSession.concept_id);
    if (matched) setCurrentConcept(matched);
  }, [activeSessionId, sessions, concepts]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (showSlideOver && slideOverTab === "graph" && currentConcept) {
      void loadSubgraph(currentConcept.concept_id);
      setGraphViewConceptId(currentConcept.concept_id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showSlideOver, slideOverTab, currentConcept?.concept_id, wsId]);

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
    tutorProtocol,
    sessionTitle,
    startNewSession,
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
    // Hierarchy
    hierarchyPath,
    // Drawers
    showSlideOver,
    slideOverTab,
    setSlideOverTab,
    drawerOpen,
    closingDrawer,
    openDrawer,
    closeDrawer,
    toggleSidebar,
    // Onboarding
    onboarding,
    // Concept activity
    conceptActivity,
  };
}
