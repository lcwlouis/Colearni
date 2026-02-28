import { ChatResponse, CollapsibleHint } from "@/components/chat-response";
import { MarkdownContent } from "@/components/markdown-content";
import type { GraphConceptSummary, OnboardingStatusResponse } from "@/lib/api/types";
import type { ChatPhase, TimelineMessage } from "../types";
import { PHASE_LABELS } from "../types";

interface TutorTimelineProps {
  timeline: TimelineMessage[];
  chatLoading: boolean;
  chatPhase: ChatPhase;
  chatError: string | null;
  streamFallback: boolean;
  onboarding: OnboardingStatusResponse | null;
  concepts: GraphConceptSummary[];
  setCurrentConcept: (concept: GraphConceptSummary | null) => void;
  setSuggestedConceptId: (id: number | null) => void;
  setQuery: (query: string) => void;
}

export function TutorTimeline({
  timeline,
  chatLoading,
  chatPhase,
  chatError,
  streamFallback,
  onboarding,
  concepts,
  setCurrentConcept,
  setSuggestedConceptId,
  setQuery,
}: TutorTimelineProps) {
  return (
    <div className="chat-timeline" aria-live="polite">
      {timeline.length === 0 && onboarding && onboarding.has_documents && onboarding.suggested_topics.length > 0 ? (
        <div className="onboarding-card">
          <h3>Welcome! Pick a topic to start learning</h3>
          <p className="onboarding-subtitle">These concepts were extracted from your documents.</p>
          <div className="onboarding-chips">
            {onboarding.suggested_topics.map((topic) => (
              <button
                key={topic.concept_id}
                type="button"
                className="onboarding-chip"
                onClick={() => {
                  const matched = concepts.find((c) => c.concept_id === topic.concept_id);
                  if (matched) setCurrentConcept(matched);
                  setSuggestedConceptId(topic.concept_id);
                  setQuery(`Teach me about ${topic.canonical_name}`);
                }}
              >
                <span className="chip-name">{topic.canonical_name}</span>
                {topic.description ? (
                  <span className="chip-desc">
                    {topic.description.length > 80 ? topic.description.slice(0, 80) + "…" : topic.description}
                  </span>
                ) : null}
              </button>
            ))}
          </div>
        </div>
      ) : timeline.length === 0 ? (
        <p className="status empty">Start chatting to build context.</p>
      ) : null}
      {timeline.map((message) => (
        <article
          key={message.id}
          className={`chat-message ${message.role === "assistant" ? "assistant" : message.role === "user" ? "user" : "system"}`}
        >
          <div className="chat-avatar">
            {message.role === "assistant" ? "🤖" : message.role === "user" ? "👤" : "⚙️"}
          </div>
          <div className="chat-content">
            <p className="chat-role">
              {message.role === "assistant" ? "Tutor" : message.role === "user" ? "You" : "System"}
            </p>
            {message.role === "assistant" && message.response ? (
              <ChatResponse response={message.response} />
            ) : (
              <>
                {message.reasoningSummary ? (
                  <p className="chat-reasoning-summary" style={{ fontSize: "0.75rem", opacity: 0.7, marginBottom: "0.25rem" }}>
                    ⚡ {message.reasoningSummary}
                  </p>
                ) : null}
                <MarkdownContent content={message.text} />
                {message.answerParts?.hint ? (
                  <CollapsibleHint hint={message.answerParts.hint} index={0} />
                ) : null}
              </>
            )}
          </div>
        </article>
      ))}

      {chatLoading && chatPhase !== "idle" ? (
        <div className="chat-status-indicator">
          <div className="chat-avatar" style={{ background: "var(--accent)", color: "#fff" }}>🤖</div>
          <div className="chat-status-content">
            <span className="chat-typing-dots" aria-hidden="true">
              <span className="dot" />
              <span className="dot" />
              <span className="dot" />
            </span>
            <span className="chat-status-label">{PHASE_LABELS[chatPhase]}</span>
            {streamFallback ? (
              <span className="chat-fallback-badge" title="Stream unavailable — using fallback mode">⚠ fallback</span>
            ) : null}
          </div>
        </div>
      ) : null}
      {chatError ? (
        <p className="status error" style={{ maxWidth: "48rem", margin: "0 auto" }}>{chatError}</p>
      ) : null}
    </div>
  );
}
