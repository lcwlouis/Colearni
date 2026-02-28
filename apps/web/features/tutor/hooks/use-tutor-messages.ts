import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "@/lib/api/client";
import type {
  AssistantResponseEnvelope,
  ConceptSwitchSuggestion,
  GraphConceptSummary,
  GroundingMode,
} from "@/lib/api/types";
import type { ChatPhase, TimelineMessage } from "../types";
import { errorText, mapMessage } from "../types";

interface UseTutorMessagesOptions {
  wsId: string | undefined;
  activeSessionId: string | null;
  currentConcept: GraphConceptSummary | null;
  concepts: GraphConceptSummary[];
  suggestedConceptId: number | null;
  switchDecisionRef: React.MutableRefObject<"accept" | "reject" | null>;
  grounding_mode: GroundingMode;
  refreshSessions: () => Promise<void>;
  setCurrentConcept: (concept: GraphConceptSummary | null) => void;
  setSwitchSuggestion: (suggestion: ConceptSwitchSuggestion | null) => void;
  setSuggestedConceptId: (id: number | null) => void;
  setSwitchDecision: (decision: "accept" | "reject" | null) => void;
}

export function useTutorMessages({
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
}: UseTutorMessagesOptions) {
  const [messages, setMessages] = useState<TimelineMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatPhase, setChatPhase] = useState<ChatPhase>("idle");
  const [chatError, setChatError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  // E1: track in-flight request so navigation cancels stale callbacks
  const chatAbortRef = useRef<AbortController | null>(null);
  const activeRequestIdRef = useRef<number>(0);

  const loadMessages = useCallback(async (sessionId: string) => {
    if (!wsId) return;
    setChatLoading(true);
    setChatError(null);
    try {
      const payload = await apiClient.getChatMessages(wsId, sessionId, {
        limit: 500,
      });
      setMessages(payload.messages.map(mapMessage));

      // Restore active concept from the latest assistant message
      for (let i = payload.messages.length - 1; i >= 0; i--) {
        const record = payload.messages[i];
        if (record.type === "assistant" && typeof record.payload === "object") {
          const candidate = record.payload as Partial<AssistantResponseEnvelope>;
          const resolvedConceptId = candidate.conversation_meta?.resolved_concept_id;
          if (resolvedConceptId) {
            setCurrentConcept(
              concepts.find((c) => c.concept_id === resolvedConceptId) ?? null,
            );
            break;
          }
        }
      }
    } catch (error: unknown) {
      setMessages([]);
      setChatError(errorText(error, "Failed to load messages"));
    } finally {
      setChatLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsId, concepts]);

  async function onSubmitChat(eventOrText: FormEvent<HTMLFormElement> | string) {
    if (typeof eventOrText !== "string") {
      eventOrText.preventDefault();
    }
    const text = typeof eventOrText === "string" ? eventOrText.trim() : query.trim();
    if (!text || !wsId || !activeSessionId) return;

    // E1: Cancel any previous in-flight request
    chatAbortRef.current?.abort();
    const abortController = new AbortController();
    chatAbortRef.current = abortController;
    const requestId = ++activeRequestIdRef.current;

    const optimisticUser: TimelineMessage = {
      id: `tmp-user-${Date.now()}`,
      role: "user",
      text,
    };
    setMessages((prev) => [...prev, optimisticUser]);
    setQuery("");
    setChatLoading(true);
    setChatPhase("thinking");
    setChatError(null);

    // E2: Simulate phase progression for UX feedback
    const phaseTimer = setTimeout(() => {
      if (requestId === activeRequestIdRef.current) {
        setChatPhase("searching");
      }
    }, 1500);
    const phaseTimer2 = setTimeout(() => {
      if (requestId === activeRequestIdRef.current) {
        setChatPhase("responding");
      }
    }, 4000);

    try {
      const response = await apiClient.respondChat(wsId, {
        session_id: activeSessionId,
        query: text,
        concept_id: currentConcept?.concept_id,
        suggested_concept_id: suggestedConceptId ?? undefined,
        concept_switch_decision: switchDecisionRef.current ?? undefined,
        grounding_mode,
      });

      if (requestId !== activeRequestIdRef.current) return;

      await loadMessages(activeSessionId);

      const resolvedConceptId = response.conversation_meta?.resolved_concept_id;
      if (resolvedConceptId) {
        const resolved = concepts.find((item) => item.concept_id === resolvedConceptId);
        if (resolved) setCurrentConcept(resolved);
      }

      if (response.conversation_meta?.concept_switch_suggestion) {
        setSwitchSuggestion(response.conversation_meta.concept_switch_suggestion);
      } else {
        setSwitchSuggestion(null);
      }

      setSuggestedConceptId(null);
      setSwitchDecision(null);
      switchDecisionRef.current = null;
      await refreshSessions();
    } catch (error: unknown) {
      if (requestId !== activeRequestIdRef.current) return;
      if (abortController.signal.aborted) return;
      setChatError(errorText(error, "Tutor request failed"));
    } finally {
      clearTimeout(phaseTimer);
      clearTimeout(phaseTimer2);
      if (requestId === activeRequestIdRef.current) {
        setChatLoading(false);
        setChatPhase("idle");
      }
    }
  }

  // E1: Abort in-flight chat request when session changes
  useEffect(() => {
    chatAbortRef.current?.abort();
    activeRequestIdRef.current++;
    setChatPhase("idle");

    if (activeSessionId) {
      void loadMessages(activeSessionId);
    } else {
      setMessages([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId]);

  return {
    messages,
    chatLoading,
    chatPhase,
    chatError,
    query,
    setQuery,
    onSubmitChat,
  };
}
