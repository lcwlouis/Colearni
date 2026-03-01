"use client";

import { FormEvent } from "react";
import { useTutorPage } from "@/features/tutor/hooks/use-tutor-page";
import { masteryLabel } from "@/features/tutor/types";
import { TutorTimeline } from "@/features/tutor/components/tutor-timeline";
import { TutorGraphDrawer } from "@/features/tutor/components/tutor-graph-drawer";
import { TutorQuizDrawer } from "@/features/tutor/components/tutor-quiz-drawer";
import { ConceptSwitchBanner } from "@/features/tutor/components/concept-switch-banner";
import type { ActionCTA, GroundingMode } from "@/lib/api/types";
import { useCallback } from "react";

export default function TutorPage() {
  const t = useTutorPage();

  const handleCtaClick = useCallback(
    (cta: ActionCTA) => {
      if (cta.action_type === "quiz_offer" || cta.action_type === "quiz_start") {
        if (cta.concept_id) {
          const matched = t.concepts.find((c) => c.concept_id === cta.concept_id);
          if (matched) t.setCurrentConcept(matched);
        }
        const doOpen = () => {
          t.openDrawer("quiz");
          if (cta.action_type === "quiz_start") void t.startLevelUp();
        };
        if (t.showGraph) t.closeDrawer("graph", doOpen);
        else doOpen();
      }
    },
    [t],
  );

  if (t.authLoading || !t.user) {
    return (
      <div className="flex items-center justify-center" style={{ height: "100%" }}>
        <p style={{ color: "var(--muted)" }}>Loading…</p>
      </div>
    );
  }

  return (
    <section className={`tutor-shell${t.drawerOpen ? " with-drawer" : ""}`}>
      <section className="chat-main">
        <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.75rem 1rem", borderBottom: "1px solid var(--line)", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span style={{ fontWeight: 600, fontSize: "1rem", color: "var(--text)" }}>Tutor Chat</span>
            {t.currentConcept && (
              <span style={{ fontSize: "0.85rem", color: "var(--muted)", marginLeft: "0.5rem" }}>
                · {t.currentConcept.canonical_name} ({masteryLabel(t.currentConcept.mastery_status, t.currentConcept.mastery_score)})
              </span>
            )}
            {t.suggestedConceptId && (
              <span style={{ fontSize: "0.85rem", color: "#eab308", marginLeft: "0.5rem" }}>
                · Suggestion pending
              </span>
            )}
          </div>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <select
              value={t.grounding_mode}
              onChange={(event) => t.setGroundingMode(event.target.value as GroundingMode)}
              style={{ fontSize: "0.85rem", padding: "0.2rem 0.5rem", borderRadius: "0.5rem", border: "1px solid var(--line)", background: "transparent", color: "var(--text)" }}
            >
              <option value="hybrid">hybrid</option>
              <option value="strict">strict</option>
            </select>
            <button
              type="button"
              className={`header-action-btn${t.showQuiz ? " active" : ""}`}
              onClick={() => {
                if (!t.showQuiz) {
                  const doOpen = () => {
                    t.openDrawer("quiz");
                    if (t.levelUpState.phase === "idle") void t.startLevelUp();
                  };
                  if (t.showGraph) t.closeDrawer("graph", doOpen);
                  else doOpen();
                } else {
                  t.closeDrawer("quiz");
                }
              }}
            >
              {t.showQuiz ? "Hide quiz" : "Level-up quiz"}
            </button>
            <button
              type="button"
              className={`header-action-btn${t.showGraph ? " active" : ""}`}
              onClick={() => {
                if (!t.showGraph) {
                  if (t.showQuiz) t.closeDrawer("quiz", () => t.openDrawer("graph"));
                  else t.openDrawer("graph");
                } else {
                  t.closeDrawer("graph");
                }
              }}
            >
              {t.showGraph ? "Hide graph" : "Show graph"}
            </button>
          </div>
        </header>

        <TutorTimeline
          timeline={t.messages}
          chatLoading={t.chatLoading}
          chatPhase={t.chatPhase}
          chatError={t.chatError}
          streamFallback={t.streamFallback}
          activitySteps={t.activitySteps}
          onboarding={t.onboarding}
          concepts={t.concepts}
          setCurrentConcept={t.setCurrentConcept}
          setSuggestedConceptId={t.setSuggestedConceptId}
          setQuery={t.setQuery}
          onCtaClick={handleCtaClick}
        />

        <div className="chat-composer-dock">
          <form className="chat-composer" onSubmit={(event: FormEvent<HTMLFormElement>) => void t.onSubmitChat(event)}>
            <textarea
              rows={1}
              value={t.query}
              onChange={(event) => {
                t.setQuery(event.target.value);
                event.target.style.height = "auto";
                event.target.style.height = `${event.target.scrollHeight}px`;
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              style={{ overflowY: "hidden", minHeight: "2.8rem", maxHeight: "12rem" }}
              placeholder="Ask a question"
              required
            />
            <button type="submit" disabled={t.chatLoading} className="send-btn" aria-label="Send">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"><path fill="currentColor" d="M4 22L22 12L4 2V9L15 12L4 15V22Z" /></svg>
            </button>
          </form>
        </div>
      </section>

      {t.showGraph ? (
        <TutorGraphDrawer
          closingDrawer={t.closingDrawer}
          currentConcept={t.currentConcept}
          graphViewConceptId={t.graphViewConceptId}
          subgraph={t.subgraph}
          conceptsLoading={t.conceptsLoading}
          conceptsError={t.conceptsError}
          loadSubgraph={t.loadSubgraph}
          setGraphViewConceptId={t.setGraphViewConceptId}
          tutorResetViewRef={t.tutorResetViewRef}
          conceptActivity={t.conceptActivity}
        />
      ) : null}

      {t.showQuiz ? (
        <TutorQuizDrawer
          closingDrawer={t.closingDrawer}
          levelUpState={t.levelUpState}
          onStartQuiz={() => void t.startLevelUp()}
          onAnswerChange={(itemId, value) =>
            t.dispatchLevelUp({ type: "answer", item_id: itemId, answer: value })
          }
          onSubmitQuiz={() => void t.submitLevelUp()}
          dispatchReset={() => t.dispatchLevelUp({ type: "reset" })}
        />
      ) : null}

      {t.switchSuggestion ? (
        <ConceptSwitchBanner
          switchSuggestion={t.switchSuggestion}
          concepts={t.concepts}
          setCurrentConcept={t.setCurrentConcept}
          setSuggestedConceptId={t.setSuggestedConceptId}
          setSwitchDecision={t.setSwitchDecision}
          switchDecisionRef={t.switchDecisionRef}
          setSwitchSuggestion={t.setSwitchSuggestion}
          onSubmitChat={(text) => void t.onSubmitChat(text)}
        />
      ) : null}
    </section>
  );
}
