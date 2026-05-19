"use client";

import { useEffect, useState, type PointerEvent } from "react";

import type { ConceptDetail, ConceptNode } from "@/lib/types";

import { TutorPanel } from "./TutorPanel";

interface ConceptPanelProps {
  workspaceId: string;
  trailId: string;
  detail: ConceptDetail;
  onClose: () => void;
  onSelectConcept?: (conceptId: string) => void;
}

export function ConceptPanel({
  workspaceId,
  trailId,
  detail,
  onClose,
  onSelectConcept,
}: ConceptPanelProps) {
  const concept = detail.concept;
  const [tutorOpen, setTutorOpen] = useState(false);
  const [mobileExpanded, setMobileExpanded] = useState(false);
  const [dragStartY, setDragStartY] = useState<number | null>(null);
  const [dragOffset, setDragOffset] = useState(0);

  useEffect(() => {
    setTutorOpen(false);
  }, [concept.id]);

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
        tutorOpen ? "md:max-w-xl" : "md:max-w-md"
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
          </div>
        </div>
        <button
          type="button"
          onPointerDown={(event) => event.stopPropagation()}
          onPointerUp={(event) => event.stopPropagation()}
          onClick={(event) => {
            event.stopPropagation();
            onClose();
          }}
          className="rounded-md border border-slate-200 px-2 py-1 text-sm text-slate-600 hover:bg-slate-50"
        >
          Close
        </button>
      </div>
      <div
        data-testid="concept-sheet-body"
        className={`flex-1 overflow-y-auto p-4 md:block md:p-5 ${
          mobileExpanded ? "block" : "hidden"
        }`}
      >
        {tutorOpen ? (
          <TutorPanel
            workspaceId={workspaceId}
            trailId={trailId}
            concept={concept}
            sources={detail.sources}
            onBack={() => setTutorOpen(false)}
          />
        ) : (
          <>
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
      {!tutorOpen ? (
        <div
          className={`border-t border-slate-200 p-4 md:block md:p-5 ${
            mobileExpanded ? "block" : "hidden"
          }`}
        >
          <button
            type="button"
            onClick={() => {
              setTutorOpen(true);
              setMobileExpanded(true);
            }}
            className="h-10 w-full rounded-md bg-blue-600 text-sm font-medium text-white hover:bg-blue-700"
          >
            Start Learning
          </button>
        </div>
      ) : null}
    </aside>
  );
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
