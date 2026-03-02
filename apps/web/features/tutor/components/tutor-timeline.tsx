import { useState } from "react";
import { ChatResponse, CollapsibleHint } from "@/components/chat-response";
import Link from "next/link";
import { OnboardingConfirm } from "./onboarding-confirm";

function WaveLabel({ text }: { text: string }) {
  return (
    <span className="wave-text">
      {text.split("").map((char, i) => (
        <span
          key={i}
          className="wave-char"
          style={{ animationDelay: `${i * 0.04}s` }}
        >
          {char === " " ? "\u00A0" : char}
        </span>
      ))}
    </span>
  );
}
import { MarkdownContent } from "@/components/markdown-content";
import type { ActionCTA, GraphConceptSummary, OnboardingStatusResponse, OnboardingSuggestedTopic } from "@/lib/api/types";
import type { ActivityStep, ChatPhase, TimelineMessage } from "../types";
import { PHASE_LABELS } from "../types";

interface TutorTimelineProps {
  timeline: TimelineMessage[];
  chatLoading: boolean;
  chatPhase: ChatPhase;
  chatError: string | null;
  streamFallback: boolean;
  activitySteps: ActivityStep[];
  onboarding: OnboardingStatusResponse | null;
  concepts: GraphConceptSummary[];
  setCurrentConcept: (concept: GraphConceptSummary | null) => void;
  setSuggestedConceptId: (id: number | null) => void;
  setQuery: (query: string) => void;
  onSend: (text: string) => void;
  onCtaClick?: (cta: ActionCTA) => void;
}

export function TutorTimeline({
  timeline,
  chatLoading,
  chatPhase,
  chatError,
  streamFallback,
  activitySteps,
  onboarding,
  concepts,
  setCurrentConcept,
  setSuggestedConceptId,
  setQuery,
  onSend,
  onCtaClick,
}: TutorTimelineProps) {
  const [confirmTopic, setConfirmTopic] = useState<OnboardingSuggestedTopic | null>(null);
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
                  setConfirmTopic(topic);
                }}
              >
                <span className="chip-name">
                    {topic.canonical_name}
                    {topic.tier ? (
                      <span className={`chip-tier chip-tier--${topic.tier}`}>{topic.tier}</span>
                    ) : null}
                  </span>
                {topic.description ? (
                  <span className="chip-desc">
                    {topic.description.length > 80 ? topic.description.slice(0, 80) + "…" : topic.description}
                  </span>
                ) : null}
              </button>
            ))}
          </div>
          {confirmTopic ? (
            <OnboardingConfirm
              conceptName={confirmTopic.canonical_name}
              onConfirm={() => {
                const matched = concepts.find((c) => c.concept_id === confirmTopic.concept_id);
                if (matched) setCurrentConcept(matched);
                setSuggestedConceptId(confirmTopic.concept_id);
                setConfirmTopic(null);
                onSend(`Teach me about ${confirmTopic.canonical_name}`);
              }}
              onCancel={() => setConfirmTopic(null)}
            />
          ) : null}
          <div className="onboarding-divider"><span>or</span></div>
          <div className="onboarding-actions">
            <Link href="/graph" className="onboarding-action-btn">
              🗺️ Browse the graph
            </Link>
            <Link href="/kb" className="onboarding-action-btn">
              📄 Upload more documents
            </Link>
          </div>
        </div>
      ) : timeline.length === 0 ? (
        <div className="onboarding-card onboarding-card--empty">
          <h3>Welcome to your learning space</h3>
          <p className="onboarding-subtitle">Upload study materials to get started, or just ask a question.</p>
          <div className="onboarding-actions">
            <Link href="/kb" className="onboarding-action-btn onboarding-action-btn--primary">
              📄 Upload your first document
            </Link>
          </div>
          <p className="onboarding-secondary-hint">Or just start chatting below</p>
        </div>
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
              <ChatResponse response={message.response} onCtaClick={onCtaClick} />
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

      {chatLoading && chatPhase !== "idle" ? (() => {
        const activeStep = activitySteps.filter((s) => !s.done).at(-1);
        const currentLabel = activeStep?.label ?? PHASE_LABELS[chatPhase];
        const statusKey = activeStep ? `${activeStep.activity}-${activeStep.label}` : chatPhase;
        return (
          <div className="chat-status-indicator">
            <div className="chat-avatar" style={{ background: "var(--accent)", color: "#fff" }}>🤖</div>
            <div className="chat-status-content">
              <span className="chat-typing-dots" aria-hidden="true">
                <span className="dot" />
                <span className="dot" />
                <span className="dot" />
              </span>
              <span className="chat-status-label" key={statusKey}>{currentLabel}</span>
              {streamFallback ? (
                <span className="chat-fallback-badge" title="Stream unavailable — using fallback mode">⚠ fallback</span>
              ) : null}
            </div>
          </div>
        );
      })() : null}
      {chatError ? (
        <p className="status error" style={{ maxWidth: "48rem", margin: "0 auto" }}>{chatError}</p>
      ) : null}
    </div>
  );
}
