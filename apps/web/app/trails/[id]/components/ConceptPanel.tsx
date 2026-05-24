"use client";

import { useState, type PointerEvent } from "react";

import type { ConceptDetail, ConceptNode, MasteryStatus } from "@/lib/types";

import { QuizPanel } from "./QuizPanel";
import { TutorPanel } from "./TutorPanel";

interface ConceptPanelProps {
  workspaceId: string;
  trailId: string;
  detail: ConceptDetail;
  onClose: () => void;
  onSelectConcept?: (conceptId: string) => void;
  onMasteryUpdated?: (conceptId: string, update: { status: MasteryStatus; score: number }) => void;
}

export function ConceptPanel({
  workspaceId,
  trailId,
  detail,
  onClose,
  onSelectConcept,
  onMasteryUpdated,
}: ConceptPanelProps) {
  const concept = detail.concept;
  const [panelWidthState, setPanelWidthState] = useState<{ conceptId: string; wide: boolean }>({
    conceptId: concept.id,
    wide: false,
  });
  const [mobileExpanded, setMobileExpanded] = useState(false);
  const [dragStartY, setDragStartY] = useState<number | null>(null);
  const [dragOffset, setDragOffset] = useState(0);
  const panelWide = panelWidthState.conceptId === concept.id ? panelWidthState.wide : false;

  function startDrag(event: PointerEvent<HTMLElement>) {
    if (event.pointerType === "mouse" && event.button !== 0) {
      return;
    }
    setDragStartY(event.clientY);
    setDragOffset(0);
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }

  function moveDrag(event: PointerEvent<HTMLElement>) {
    if (dragStartY === null) {
      return;
    }
    setDragOffset(event.clientY - dragStartY);
  }

  function endDrag(event: PointerEvent<HTMLElement>) {
    if (dragStartY === null) {
      return;
    }
    event.currentTarget.releasePointerCapture?.(event.pointerId);
    if (dragOffset < -40) {
      setMobileExpanded(true);
    } else if (dragOffset > 40) {
      setMobileExpanded(false);
    }
    setDragStartY(null);
    setDragOffset(0);
  }

  return (
    <aside
      className={`absolute inset-x-0 bottom-0 z-20 flex w-full flex-col rounded-t-xl border-t border-slate-200 bg-white shadow-xl transition-[max-height,transform] duration-200 ease-out md:inset-y-0 md:left-auto md:right-0 md:h-full md:max-h-none md:translate-y-0 md:rounded-none md:border-l md:border-t-0 ${
        panelWide ? "md:max-w-xl" : "md:max-w-md"
      } ${
        mobileExpanded ? "max-h-[78vh]" : "max-h-48"
      }`}
      style={
        dragStartY === null
          ? undefined
          : { transform: `translateY(${Math.max(-40, Math.min(72, dragOffset))}px)` }
      }
    >
        <button
          type="button"
          aria-label={mobileExpanded ? "Collapse concept details" : "Expand concept details"}
          onClick={() => setMobileExpanded((current) => !current)}
          onPointerDown={startDrag}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          className="touch-none px-4 pt-2 md:hidden"
        >
          <span className="mx-auto block h-1 w-10 rounded-full bg-slate-300" />
        </button>
      <div
        onPointerDown={startDrag}
        onPointerMove={moveDrag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        className="flex touch-none items-start justify-between gap-4 border-b border-slate-200 p-4 md:p-5"
      >
        <div>
          <h2 className="text-lg font-semibold text-slate-950 md:text-xl">{concept.title}</h2>
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <Badge>{concept.concept_level}</Badge>
            <Badge>{concept.bloom_level}</Badge>
            <Badge>{concept.difficulty}</Badge>
            <Badge>{concept.node_type}</Badge>
            <Badge>{detail.mastery.status}</Badge>
          </div>
        </div>
        <button
          type="button"
          aria-label="Close"
          onPointerDown={(event) => event.stopPropagation()}
          onPointerUp={(event) => event.stopPropagation()}
          onClick={(event) => {
            event.stopPropagation();
            onClose();
          }}
          className="grid size-8 place-items-center rounded-md border border-slate-200 text-lg leading-none text-slate-600 hover:bg-slate-50"
        >
          ×
        </button>
      </div>
      <ConceptPanelBody
        key={concept.id}
        workspaceId={workspaceId}
        trailId={trailId}
        detail={detail}
        onSelectConcept={onSelectConcept}
        onMasteryUpdated={onMasteryUpdated}
        mobileExpanded={mobileExpanded}
        setMobileExpanded={setMobileExpanded}
        setPanelWide={(wide) =>
          setPanelWidthState({ conceptId: concept.id, wide })
        }
      />
    </aside>
  );
}

function ConceptPanelBody({
  workspaceId,
  trailId,
  detail,
  onSelectConcept,
  onMasteryUpdated,
  mobileExpanded,
  setMobileExpanded,
  setPanelWide,
}: {
  workspaceId: string;
  trailId: string;
  detail: ConceptDetail;
  onSelectConcept?: (conceptId: string) => void;
  onMasteryUpdated?: (conceptId: string, update: { status: MasteryStatus; score: number }) => void;
  mobileExpanded: boolean;
  setMobileExpanded: (value: boolean | ((current: boolean) => boolean)) => void;
  setPanelWide: (wide: boolean) => void;
}) {
  const concept = detail.concept;
  const [tutorOpen, setTutorOpen] = useState(false);
  const [quizMode, setQuizMode] = useState<"level_up" | "practice" | null>(null);

  return (
    <>
      <div
        data-testid="concept-sheet-body"
        className={`flex-1 ${
          tutorOpen ? "min-h-0 overflow-hidden p-0 md:p-0" : "overflow-y-auto p-4 md:block md:p-5"
        } ${mobileExpanded ? "block" : "hidden"}`}
      >
        {tutorOpen ? (
          <TutorPanel
            workspaceId={workspaceId}
            trailId={trailId}
            concept={concept}
            sources={detail.sources}
            onBack={() => {
              setTutorOpen(false);
              setPanelWide(false);
            }}
            onMasteryUpdated={onMasteryUpdated}
          />
        ) : quizMode ? (
          <QuizPanel
            workspaceId={workspaceId}
            trailId={trailId}
            conceptId={concept.id}
            mode={quizMode}
            onBack={() => {
              setQuizMode(null);
              setPanelWide(false);
            }}
            onMasteryUpdated={onMasteryUpdated}
          />
        ) : (
          <>
            <section data-testid="why-it-matters" className="rounded-md border border-slate-100 bg-slate-50 p-3 text-sm text-slate-700">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                Why this concept
              </p>
              <p className="mt-1 leading-5">
                {whyItMatters(concept.concept_level, concept.bloom_level, concept.difficulty)}
              </p>
            </section>

            <Section title="Prerequisites" nodes={detail.prerequisites} onSelect={onSelectConcept} />
            <Section title="Contained by" nodes={detail.containing_nodes} onSelect={onSelectConcept} />
            <Section title="Contains" nodes={detail.contained_nodes} onSelect={onSelectConcept} />
            <Section title="Related" nodes={detail.related} onSelect={onSelectConcept} />

            <section className="mt-6">
              <h3 className="text-sm font-semibold text-slate-900">Mastery checks</h3>
              <div className="mt-3 flex flex-wrap gap-2">
                {concept.mastery_check_labels.length === 0 ? (
                  <p className="text-sm text-slate-500">No checks yet.</p>
                ) : (
                  concept.mastery_check_labels.map((label) => <Badge key={label}>{label}</Badge>)
                )}
              </div>
            </section>

            <section className="mt-6">
              <h3 className="text-sm font-semibold text-slate-900">Sources</h3>
              {detail.sources.length === 0 ? (
                <p className="mt-2 text-sm text-slate-500">No sources linked yet.</p>
              ) : (
                <div className="mt-3 flex flex-wrap gap-2">
                  {detail.sources.map((source) =>
                    source.url ? (
                      <a
                        key={source.id}
                        href={source.url}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-medium text-slate-700 hover:border-blue-300 hover:text-blue-700"
                      >
                        {source.title}
                      </a>
                    ) : (
                      <Badge key={source.id}>{source.title}</Badge>
                    ),
                  )}
                </div>
              )}
            </section>
          </>
        )}
      </div>
      {!tutorOpen && !quizMode ? (
        <div
          data-testid="concept-actions"
          className={`border-t border-slate-200 p-4 md:block md:p-5 ${
            mobileExpanded ? "block" : "hidden"
          }`}
        >
          <ConceptActions
            status={detail.mastery.status}
            onOpenTutor={() => {
              setTutorOpen(true);
              setPanelWide(true);
              setMobileExpanded(true);
            }}
            onOpenLevelUp={() => {
              setQuizMode("level_up");
              setPanelWide(false);
              setMobileExpanded(true);
            }}
            onOpenPractice={() => {
              setQuizMode("practice");
              setPanelWide(false);
              setMobileExpanded(true);
            }}
          />
        </div>
      ) : null}
    </>
  );
}

function ConceptActions({
  status,
  onOpenTutor,
  onOpenLevelUp,
  onOpenPractice,
}: {
  status: MasteryStatus;
  onOpenTutor: () => void;
  onOpenLevelUp: () => void;
  onOpenPractice: () => void;
}) {
  // CTA hierarchy by mastery state (see docs/FRONTEND.md):
  //   not_started   -> Start Learning      (tutor)
  //   learning      -> Continue Tutor      (tutor)
  //   needs_review  -> Review Weak Points  (tutor, repair-oriented)
  //   mastered      -> Practice / Explore Further  (practice quiz)
  let primaryLabel: string;
  let primaryAction: () => void;
  let helper: string;
  if (status === "mastered") {
    primaryLabel = "Practice / Explore Further";
    primaryAction = onOpenPractice;
    helper = "Mastered. Practice to keep it sharp or explore further.";
  } else if (status === "needs_review") {
    primaryLabel = "Review Weak Points";
    primaryAction = onOpenTutor;
    helper = "Marked for review — revisit weak spots with the tutor.";
  } else if (status === "learning") {
    primaryLabel = "Continue Tutor";
    primaryAction = onOpenTutor;
    helper = "Pick up the Socratic conversation where you left off.";
  } else {
    primaryLabel = "Start Learning";
    primaryAction = onOpenTutor;
    helper = "Begin a guided Socratic walk-through of this concept.";
  }

  return (
    <div>
      <button
        type="button"
        onClick={primaryAction}
        className="h-10 w-full rounded-md bg-blue-600 text-sm font-medium text-white hover:bg-blue-700"
      >
        {primaryLabel}
      </button>
      <p className="mt-2 text-xs text-slate-500">{helper}</p>
      <div className="mt-3 flex gap-2">
        {status === "mastered" ? (
          <button
            type="button"
            onClick={onOpenTutor}
            className="h-9 flex-1 rounded-md border border-slate-200 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Open Tutor
          </button>
        ) : (
          <button
            type="button"
            onClick={onOpenPractice}
            className="h-9 flex-1 rounded-md border border-slate-200 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Practice
          </button>
        )}
        <button
          type="button"
          onClick={onOpenLevelUp}
          className="h-9 flex-1 rounded-md border border-slate-200 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Level Up
        </button>
      </div>
    </div>
  );
}

function whyItMatters(level: string, bloom: string, difficulty: string): string {
  const levelText =
    level === "umbrella"
      ? "a broad area you'll unpack into smaller topics"
      : level === "topic"
        ? "a core topic in this Trail"
        : level === "subtopic"
          ? "a focused unit inside a topic"
          : "an atomic skill or check";
  return `This is ${levelText}. Goal: reach ${bloom} (${difficulty}).`;
}

function Section({
  title,
  nodes,
  onSelect,
}: {
  title: string;
  nodes: ConceptNode[];
  onSelect?: (conceptId: string) => void;
}) {
  return (
    <section className="mt-6 first:mt-0">
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      {nodes.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">None</p>
      ) : (
        <ul className="mt-2 grid gap-2">
          {nodes.map((node) => (
            <li key={node.id}>
              <button
                type="button"
                onClick={() => onSelect?.(node.id)}
                className="w-full rounded-md border border-slate-200 px-3 py-2 text-left text-sm text-slate-700 hover:bg-slate-50"
              >
                {node.title}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded border border-slate-200 bg-slate-50 px-2 py-1 font-medium text-slate-700">
      {children}
    </span>
  );
}
