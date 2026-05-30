"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type PointerEvent,
  type ReactNode,
} from "react";
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Circle,
  type LucideIcon,
} from "lucide-react";

import {
  getConceptSources,
  linkSourceToConcept,
  streamConceptPrimer,
  uploadSource,
} from "@/lib/api";
import type {
  ConceptDetail,
  ConceptNode,
  ConceptPrimerKeyTerm,
  ConceptPrimerRead,
  ConceptSourceListItem,
  MasteryStatus,
} from "@/lib/types";
import { titleCase } from "@/lib/display";

import { QuizPanel } from "./QuizPanel";
import { TutorPanel } from "./TutorPanel";

// Dedupe in-flight primer streams per concept so React StrictMode's
// double-invoked effects (and rapid re-opens) never open duplicate SSE
// connections. The handle exposes the resolution promise plus live token
// buffers (reasoning + output) that subscribers can render as a streaming
// preview.
interface PrimerStreamHandle {
  promise: Promise<ConceptPrimerRead>;
  buffer: string;
  thinking: string;
  listeners: Set<() => void>;
}

const primerStreamRequests = new Map<string, PrimerStreamHandle>();

interface ConceptPanelProps {
  workspaceId: string;
  trailId: string;
  detail: ConceptDetail;
  onClose: () => void;
  onSelectConcept?: (conceptId: string) => void;
  onMasteryUpdated?: (
    conceptId: string,
    update: { status: MasteryStatus; score: number },
  ) => void;
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
  const [panelWidthState, setPanelWidthState] = useState<{
    conceptId: string;
    wide: boolean;
  }>({
    conceptId: concept.id,
    wide: false,
  });
  const [mobileExpanded, setMobileExpanded] = useState(false);
  const [dragStartY, setDragStartY] = useState<number | null>(null);
  const [dragOffset, setDragOffset] = useState(0);
  const panelWide =
    panelWidthState.conceptId === concept.id ? panelWidthState.wide : false;

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
      } ${mobileExpanded ? "max-h-[78vh]" : "max-h-48"}`}
      style={
        dragStartY === null
          ? undefined
          : {
              transform: `translateY(${Math.max(-40, Math.min(72, dragOffset))}px)`,
            }
      }
    >
      <button
        type="button"
        aria-label={
          mobileExpanded ? "Collapse concept details" : "Expand concept details"
        }
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
          <h2 className="text-lg font-semibold text-slate-950 md:text-xl">
            {concept.title}
          </h2>
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <Badge>{titleCase(concept.concept_level)}</Badge>
            <Badge>{titleCase(concept.bloom_level)}</Badge>
            <Badge>{titleCase(concept.difficulty)}</Badge>
            <Badge>{titleCase(concept.node_type)}</Badge>
            <MasteryBadge status={detail.mastery.status} />
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
  onMasteryUpdated?: (
    conceptId: string,
    update: { status: MasteryStatus; score: number },
  ) => void;
  mobileExpanded: boolean;
  setMobileExpanded: (value: boolean | ((current: boolean) => boolean)) => void;
  setPanelWide: (wide: boolean) => void;
}) {
  const concept = detail.concept;
  const [tutorOpen, setTutorOpen] = useState(false);
  const [quizMode, setQuizMode] = useState<"level_up" | "practice" | null>(
    null,
  );
  // Seed welcome suggestions from a cached primer; PrimerSection reports the
  // freshly streamed primer up so the tutor can use its sample questions.
  const [sampleQuestions, setSampleQuestions] = useState<string[]>(
    detail.primer?.sample_questions ?? [],
  );
  // Stable identity so PrimerSection's streaming effect doesn't re-run (and
  // re-stream) every time this body re-renders.
  const handlePrimerLoaded = useCallback((primer: ConceptPrimerRead) => {
    setSampleQuestions(primer.sample_questions ?? []);
  }, []);

  return (
    <>
      <div
        data-testid="concept-sheet-body"
        className={`flex-1 ${
          tutorOpen
            ? "min-h-0 overflow-hidden p-0 md:p-0"
            : "overflow-y-auto p-4 md:block md:p-5"
        } ${mobileExpanded ? "block" : "hidden"}`}
      >
        {tutorOpen ? (
          <TutorPanel
            workspaceId={workspaceId}
            trailId={trailId}
            concept={concept}
            sources={detail.sources}
            sampleQuestions={sampleQuestions}
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
            <PrimerSection
              workspaceId={workspaceId}
              trailId={trailId}
              conceptId={concept.id}
              initialPrimer={detail.primer ?? null}
              onPrimerLoaded={handlePrimerLoaded}
            />

            <Section
              title="Prerequisites"
              nodes={detail.prerequisites}
              onSelect={onSelectConcept}
            />
            <Section
              title="Contained by"
              nodes={detail.containing_nodes}
              onSelect={onSelectConcept}
            />
            <Section
              title="Contains"
              nodes={detail.contained_nodes}
              onSelect={onSelectConcept}
            />
            <Section
              title="Related"
              nodes={detail.related}
              onSelect={onSelectConcept}
            />

            <section className="mt-6">
              <h3 className="text-sm font-semibold text-slate-900">
                Mastery checks
              </h3>
              <div className="mt-3 flex flex-wrap gap-2">
                {concept.mastery_check_labels.length === 0 ? (
                  <p className="text-sm text-slate-500">No checks yet.</p>
                ) : (
                  concept.mastery_check_labels.map((label) => (
                    <Badge key={label}>{label}</Badge>
                  ))
                )}
              </div>
            </section>

            <section className="mt-6">
              <SourcesSection
                workspaceId={workspaceId}
                conceptId={concept.id}
              />
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

function PrimerSection({
  workspaceId,
  trailId,
  conceptId,
  initialPrimer,
  onPrimerLoaded,
}: {
  workspaceId: string;
  trailId: string;
  conceptId: string;
  initialPrimer: ConceptPrimerRead | null;
  onPrimerLoaded?: (primer: ConceptPrimerRead) => void;
}) {
  const [primer, setPrimer] = useState<ConceptPrimerRead | null>(initialPrimer);
  // State is seeded from the cached primer (if any); only stream when absent.
  const [loading, setLoading] = useState(!initialPrimer);
  const [failed, setFailed] = useState(false);
  // Raw token buffers streamed in while the primer is being written. These are
  // a cosmetic preview only — the authoritative render comes from `done`.
  // `preview` is the model's output text; `thinkingPreview` is its reasoning,
  // which (on reasoning models) streams first while the output is still empty.
  const [preview, setPreview] = useState("");
  const [thinkingPreview, setThinkingPreview] = useState("");

  useEffect(() => {
    // A cached primer arrived with the concept detail; nothing to stream.
    // The subtree remounts per concept (keyed in ConceptPanelBody), so the
    // seeded initial state already reflects it. Also bail once we already have
    // a primer so a parent re-render can never re-open the stream.
    if (initialPrimer || primer) {
      return;
    }

    let cancelled = false;
    const handle = getOrCreatePrimerStream(workspaceId, trailId, conceptId);
    // Updates flow through the subscriber callback (the supported effect
    // pattern); the listener also fires for already-buffered tokens when
    // re-subscribing under StrictMode's double-invoke.
    const listener = () => {
      if (!cancelled) {
        setPreview(handle.buffer);
        setThinkingPreview(handle.thinking);
      }
    };
    handle.listeners.add(listener);
    if (handle.buffer || handle.thinking) {
      listener();
    }

    handle.promise
      .then((result) => {
        if (!cancelled) {
          setPrimer(result);
          onPrimerLoaded?.(result);
        }
      })
      .catch(() => {
        // Primer streaming is best-effort orientation content: never crash
        // the panel.
        if (!cancelled) {
          setFailed(true);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      handle.listeners.delete(listener);
    };
  }, [workspaceId, trailId, conceptId, initialPrimer, primer, onPrimerLoaded]);

  if (failed && !primer) {
    // Graceful empty state — the rest of the panel stays usable.
    return null;
  }

  if (loading && !primer) {
    // Two-phase generating experience driven off BOTH live buffers. Reasoning
    // models emit thinking tokens for most of the duration and only burst the
    // JSON output near the end, so we lead with the reasoning preview (calm
    // sweeping shimmer + per-character fade-in) for continuous movement, then
    // switch to rendering the REAL primer sections the moment the token buffer
    // yields a parseable `overview`. The structured view is purely cosmetic —
    // the authoritative render still comes from `done`. The flat left-accent
    // treatment mirrors the chain-of-thought reasoning block.
    const partial = parsePartialPrimer(preview);
    const reasoningTail = formatReasoningPreview(thinkingPreview);
    // Structured sections take over as soon as any overview prose or a complete
    // key-term object has arrived; until then reasoning fills the early phase.
    const hasStructured =
      partial.overview.trim().length > 0 || partial.keyTerms.length > 0;
    const showReasoning = !hasStructured && reasoningTail.length > 0;
    const showSkeleton = !hasStructured && !showReasoning;
    return (
      <section
        data-testid="primer-loading"
        className="mt-6 border-l-2 border-slate-200 pl-3 dark:border-slate-700"
      >
        <p className="flex items-center gap-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          <BookOpen className="size-3.5 shrink-0" aria-hidden />
          <span>Preparing overview…</span>
          <span
            aria-hidden
            className="size-1.5 animate-pulse rounded-full bg-blue-500"
          />
        </p>
        {hasStructured ? (
          // Structured phase — the real sections parse in progressively: the
          // Overview prose grows in, then key-term cards appear one-by-one as
          // each object completes in the partial JSON.
          <div className="mt-2">
            {partial.overview.trim().length > 0 ? (
              <StreamingProse text={partial.overview} />
            ) : (
              <span
                aria-hidden
                className="mt-2 block h-4 w-2/3 animate-pulse rounded bg-slate-100 dark:bg-slate-800"
              />
            )}
            {partial.keyTerms.length > 0 ? (
              <KeyTerms terms={partial.keyTerms} />
            ) : null}
          </div>
        ) : showReasoning ? (
          // Reasoning phase — keep the sweeping-shimmer reasoning preview moving
          // while the model thinks, before any JSON output arrives.
          <div className="mt-2">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
              Reasoning
            </p>
            <PrimerStreamPreview text={reasoningTail} variant="thinking" />
          </div>
        ) : null}
        {showSkeleton ? (
          // No tokens yet — a subtle shimmer line until the stream starts.
          <span
            aria-hidden
            className="mt-1 block h-4 w-2/3 animate-pulse rounded bg-slate-100 dark:bg-slate-800"
          />
        ) : null}
      </section>
    );
  }

  if (!primer) {
    return null;
  }

  return (
    <section data-testid="primer-section" className="mt-6">
      <h3 className="text-sm font-semibold text-slate-900">Overview</h3>
      <p className="mt-2 text-sm leading-5 text-slate-700">{primer.overview}</p>

      {primer.key_terms.length > 0 ? (
        <KeyTerms terms={primer.key_terms} />
      ) : null}
    </section>
  );
}

// Shared Key-terms layout used by both the streamed (generating) state and the
// authoritative final primer so terms keep an identical look as they arrive
// one-by-one.
function KeyTerms({ terms }: { terms: ConceptPrimerKeyTerm[] }) {
  return (
    <div className="mt-4">
      <h4 className="text-xs font-medium uppercase tracking-wide text-slate-500">
        Key terms
      </h4>
      <dl className="mt-2 grid gap-2">
        {terms.map((item) => (
          <div
            key={item.term}
            className="rounded-md border border-slate-200 p-3"
          >
            <dt className="text-sm font-medium text-slate-800">{item.term}</dt>
            <dd className="mt-1 text-sm leading-5 text-slate-600">
              {item.definition}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

// --- Tolerant partial-JSON primer parsing --------------------------------
//
// The token buffer streams the model's raw output JSON
// (`{"overview": "...", "key_terms": [{"term","definition"}...], ...}`)
// character-by-character. These helpers progressively pull the real primer
// sections out of that partial buffer so the generating view can render the
// Overview prose and key-term cards as they arrive, instead of raw text. They
// are deliberately tolerant: they NEVER throw on partial or invalid JSON and
// simply return whatever has fully arrived so far. The authoritative render
// still comes from the parsed `done` payload.

// Decode a JSON string literal whose opening quote is at `openQuoteIndex`.
// Returns the decoded value plus whether the closing quote has arrived. Stops
// gracefully (complete=false) if the buffer ends mid-string or mid-escape.
function decodeJsonStringAt(
  buffer: string,
  openQuoteIndex: number,
): { value: string; endIndex: number; complete: boolean } {
  let value = "";
  let i = openQuoteIndex + 1;
  while (i < buffer.length) {
    const ch = buffer[i];
    if (ch === "\\") {
      const next = buffer[i + 1];
      if (next === undefined) {
        // Escape sequence hasn't fully arrived yet.
        return { value, endIndex: i, complete: false };
      }
      switch (next) {
        case '"':
          value += '"';
          i += 2;
          break;
        case "\\":
          value += "\\";
          i += 2;
          break;
        case "/":
          value += "/";
          i += 2;
          break;
        case "n":
          value += "\n";
          i += 2;
          break;
        case "t":
          value += "\t";
          i += 2;
          break;
        case "r":
          value += "\r";
          i += 2;
          break;
        case "b":
          value += "\b";
          i += 2;
          break;
        case "f":
          value += "\f";
          i += 2;
          break;
        case "u": {
          const hex = buffer.slice(i + 2, i + 6);
          if (hex.length < 4) {
            // Unicode escape still streaming in.
            return { value, endIndex: i, complete: false };
          }
          const code = Number.parseInt(hex, 16);
          if (Number.isNaN(code)) {
            i += 2;
          } else {
            value += String.fromCharCode(code);
            i += 6;
          }
          break;
        }
        default:
          value += next;
          i += 2;
          break;
      }
      continue;
    }
    if (ch === '"') {
      return { value, endIndex: i, complete: true };
    }
    value += ch;
    i += 1;
  }
  // Ran out of buffer before the closing quote.
  return { value, endIndex: buffer.length, complete: false };
}

// Pull the (possibly still-growing) value of a top-level string field out of a
// partial buffer. Returns "" until the key, its colon, and an opening quote
// have all arrived. Never throws.
function extractStringField(buffer: string, key: string): string {
  const needle = `"${key}"`;
  const keyIndex = buffer.indexOf(needle);
  if (keyIndex === -1) {
    return "";
  }
  const colonIndex = buffer.indexOf(":", keyIndex + needle.length);
  if (colonIndex === -1) {
    return "";
  }
  const quoteIndex = buffer.indexOf('"', colonIndex + 1);
  if (quoteIndex === -1) {
    return "";
  }
  return decodeJsonStringAt(buffer, quoteIndex).value;
}

// Pull the growing `overview` string from the partial buffer.
function extractStreamingOverview(buffer: string): string {
  return extractStringField(buffer, "overview");
}

// Scan from a `{` at `openIndex` to its matching `}`, respecting string
// literals (and their escapes) so braces inside strings don't fool the depth
// counter. Returns whether the object has fully closed.
function scanObject(
  buffer: string,
  openIndex: number,
): { endIndex: number; complete: boolean } {
  let depth = 0;
  let inString = false;
  let i = openIndex;
  while (i < buffer.length) {
    const ch = buffer[i];
    if (inString) {
      if (ch === "\\") {
        i += 2;
        continue;
      }
      if (ch === '"') {
        inString = false;
      }
      i += 1;
      continue;
    }
    if (ch === '"') {
      inString = true;
    } else if (ch === "{") {
      depth += 1;
    } else if (ch === "}") {
      depth -= 1;
      if (depth === 0) {
        return { endIndex: i, complete: true };
      }
    }
    i += 1;
  }
  return { endIndex: buffer.length, complete: false };
}

// Parse a single, fully-arrived `{ "term", "definition" }` object. Prefers a
// strict JSON.parse, with a tolerant field-extraction fallback. Returns null
// when there's no usable `term`.
function parseKeyTerm(objText: string): ConceptPrimerKeyTerm | null {
  try {
    const parsed = JSON.parse(objText) as Record<string, unknown>;
    const term = typeof parsed.term === "string" ? parsed.term : "";
    const definition =
      typeof parsed.definition === "string" ? parsed.definition : "";
    if (!term) {
      return null;
    }
    return { term, definition };
  } catch {
    const term = extractStringField(objText, "term");
    if (!term) {
      return null;
    }
    return { term, definition: extractStringField(objText, "definition") };
  }
}

// Brace-scan the `key_terms` array and emit only the objects that have fully
// arrived (a complete, balanced `{...}`). Objects still streaming in are
// skipped so cards only appear once their term+definition are stable.
function extractCompleteKeyTerms(buffer: string): ConceptPrimerKeyTerm[] {
  const terms: ConceptPrimerKeyTerm[] = [];
  const keyIndex = buffer.indexOf('"key_terms"');
  if (keyIndex === -1) {
    return terms;
  }
  const bracketIndex = buffer.indexOf("[", keyIndex);
  if (bracketIndex === -1) {
    return terms;
  }
  let i = bracketIndex + 1;
  while (i < buffer.length) {
    const ch = buffer[i];
    if (ch === "]") {
      break;
    }
    if (ch === "{") {
      const obj = scanObject(buffer, i);
      if (!obj.complete) {
        // This object is still arriving; stop — nothing past it is stable.
        break;
      }
      const parsed = parseKeyTerm(buffer.slice(i, obj.endIndex + 1));
      if (parsed) {
        terms.push(parsed);
      }
      i = obj.endIndex + 1;
    } else {
      i += 1;
    }
  }
  return terms;
}

// Combine the tolerant extractors into the partial primer the generating view
// renders. Strips any leading ```json / ``` code fences first. Never throws.
function parsePartialPrimer(buffer: string): {
  overview: string;
  keyTerms: ConceptPrimerKeyTerm[];
} {
  const cleaned = buffer.replace(/```[a-zA-Z]*\n?/g, "").replace(/```/g, "");
  return {
    overview: extractStreamingOverview(cleaned),
    keyTerms: extractCompleteKeyTerms(cleaned),
  };
}

// Roll the reasoning (thinking) buffer to its last few lines for a calm,
// muted live preview. Reasoning is plain prose (no JSON fences), so this only
// trims to a rolling window and must never throw.
function formatReasoningPreview(buffer: string): string {
  if (!buffer) {
    return "";
  }
  const cleaned = buffer.replace(/\r/g, "");
  const lines = cleaned.split("\n").filter((line) => line.trim().length > 0);
  const tail = lines.slice(-5).join("\n").trimStart();
  return tail.length > 400 ? tail.slice(-400) : tail;
}

function getOrCreatePrimerStream(
  workspaceId: string,
  trailId: string,
  conceptId: string,
): PrimerStreamHandle {
  const key = [workspaceId, trailId, conceptId].join(":");
  const existing = primerStreamRequests.get(key);
  if (existing) {
    return existing;
  }

  const handle: PrimerStreamHandle = {
    // Assigned synchronously below before the map is read by any subscriber.
    promise: undefined as unknown as Promise<ConceptPrimerRead>,
    buffer: "",
    thinking: "",
    listeners: new Set(),
  };

  let resolved: ConceptPrimerRead | null = null;
  handle.promise = streamConceptPrimer(workspaceId, trailId, conceptId, {
    onThinking: (content) => {
      handle.thinking += content;
      handle.listeners.forEach((listener) => listener());
    },
    onToken: (content) => {
      handle.buffer += content;
      handle.listeners.forEach((listener) => listener());
    },
    onStatus: () => {
      handle.listeners.forEach((listener) => listener());
    },
    onDone: (result) => {
      resolved = result;
    },
  })
    .then(() => {
      if (!resolved) {
        throw new Error("Primer stream produced no result");
      }
      return resolved;
    })
    .finally(() => {
      if (primerStreamRequests.get(key) === handle) {
        primerStreamRequests.delete(key);
      }
    });

  primerStreamRequests.set(key, handle);
  return handle;
}

// Renders the latest few lines of the raw primer stream as a calm, muted,
// rolling window — mirroring the trails generation `StreamPreview`. The text it
// receives is already trimmed to a rolling tail by `formatPrimerPreview`, so as
// new tokens arrive the window scrolls: the already-seen prefix renders as
// stable text while only the newest delta gets a gentle per-character fade-in,
// followed by a blinking cursor. `freshOffset` tolerates the window rolling
// (the prefix dropping characters off the front) so animation stays smooth.
function freshOffset(prev: string, curr: string): number {
  if (curr.startsWith(prev)) return prev.length; // no rolling yet
  for (let d = 1; d <= prev.length; d++) {
    if (curr.startsWith(prev.slice(d))) return prev.length - d;
  }
  return 0;
}

// Renders the latest few lines of a raw primer stream as a calm, muted, rolling
// window — mirroring the trails generation `StreamPreview`. The text it receives
// is already trimmed to a rolling tail, so as new tokens arrive the window
// scrolls: the already-seen prefix renders as stable text while only the newest
// delta gets a gentle per-character fade-in, under a sweeping shimmer overlay
// and followed by a blinking block cursor. `freshOffset` tolerates the window
// rolling (the prefix dropping characters off the front) so the animation stays
// smooth. `variant="thinking"` de-emphasises the reasoning channel.
function PrimerStreamPreview({
  text,
  variant = "output",
}: {
  text: string;
  variant?: "output" | "thinking";
}) {
  const isThinking = variant === "thinking";
  const prevRef = useRef("");
  const [stable, setStable] = useState("");
  const [fresh, setFresh] = useState("");
  // Incrementing key remounts the fresh span so the CSS animations restart on
  // every new chunk.
  const [epoch, setEpoch] = useState(0);

  useEffect(() => {
    const prev = prevRef.current;
    const offset = freshOffset(prev, text);
    setStable(text.slice(0, offset));
    setFresh(text.slice(offset));
    setEpoch((value) => value + 1);
    prevRef.current = text;
  }, [text]);

  // Calm, flat slate palette so the preview reads cleanly on the light panel.
  // Thinking text is de-emphasised (lighter + italic) versus the output.
  const shimmerColor = "rgba(148,163,184,0.16)";
  const textColor = isThinking
    ? "italic text-slate-500 dark:text-slate-400"
    : "text-slate-600 dark:text-slate-300";
  const cursorColor = isThinking ? "text-slate-400" : "text-slate-500";

  return (
    <div className="relative mt-1 max-h-16 overflow-hidden rounded-sm">
      {/* sweeping shimmer overlay */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background: `linear-gradient(90deg, transparent 20%, ${shimmerColor} 50%, transparent 80%)`,
          backgroundSize: "200% 100%",
          animation: "stream-shimmer 1.8s linear infinite",
        }}
      />
      <pre
        className={`relative text-xs leading-5 break-all whitespace-pre-wrap ${textColor}`}
      >
        {/* characters already visible — no animation */}
        <span>{stable}</span>
        {/* fresh characters animate in one by one */}
        <span key={epoch}>
          {fresh.split("").map((ch, index) => (
            <span
              key={index}
              style={{
                display: "inline",
                opacity: 0,
                animation: "stream-char-in 80ms ease-out both",
                animationDelay: `${index * 3}ms`,
              }}
            >
              {ch}
            </span>
          ))}
        </span>
        {/* blinking block cursor */}
        <span
          aria-hidden
          className={cursorColor}
          style={{ animation: "stream-cursor 0.9s step-end infinite" }}
        >
          ▋
        </span>
      </pre>
    </div>
  );
}

// Renders the streaming `overview` as real, flowing prose during the structured
// generating phase. Unlike `PrimerStreamPreview` this is NOT a rolling window
// and has no max-height clamp — the overview only grows, so the whole text
// stays visible and reads as the final paragraph filling in. Only the newest
// delta gets a gentle per-character fade-in; a faint cursor keeps the "still
// generating" affordance. Matches the final primer's Overview typography so the
// switch to the authoritative render on `done` is seamless.
function StreamingProse({ text }: { text: string }) {
  const prevRef = useRef("");
  const [stable, setStable] = useState("");
  const [fresh, setFresh] = useState("");
  // Incrementing key remounts the fresh span so the fade-in restarts per chunk.
  const [epoch, setEpoch] = useState(0);

  useEffect(() => {
    const prev = prevRef.current;
    // The overview grows monotonically, so the previously-shown text is simply
    // the stable prefix when the new text extends it; otherwise reset cleanly.
    if (text.startsWith(prev)) {
      setStable(prev);
      setFresh(text.slice(prev.length));
    } else {
      setStable("");
      setFresh(text);
    }
    setEpoch((value) => value + 1);
    prevRef.current = text;
  }, [text]);

  return (
    <p className="mt-2 text-sm leading-5 text-slate-700 dark:text-slate-300">
      {/* text already shown — no animation */}
      <span>{stable}</span>
      {/* newest delta fades in one character at a time */}
      <span key={epoch}>
        {fresh.split("").map((ch, index) => (
          <span
            key={index}
            style={{
              display: "inline",
              opacity: 0,
              animation: "stream-char-in 80ms ease-out both",
              animationDelay: `${index * 3}ms`,
            }}
          >
            {ch}
          </span>
        ))}
      </span>
      {/* faint trailing cursor while more prose streams in */}
      <span
        aria-hidden
        className="text-slate-400"
        style={{ animation: "stream-cursor 0.9s step-end infinite" }}
      >
        ▋
      </span>
    </p>
  );
}

type ConceptSourcesState = {
  key: string;
  sources: ConceptSourceListItem[];
  loading: boolean;
  loadError: string | null;
};

function loadingConceptSourcesState(key: string): ConceptSourcesState {
  return {
    key,
    sources: [],
    loading: true,
    loadError: null,
  };
}

function SourcesSection({
  workspaceId,
  conceptId,
}: {
  workspaceId: string;
  conceptId: string;
}) {
  const sourcesKey = `${workspaceId}:${conceptId}`;
  const [sourceState, setSourceState] = useState<ConceptSourcesState>(() =>
    loadingConceptSourcesState(sourcesKey),
  );
  const currentSourceState =
    sourceState.key === sourcesKey
      ? sourceState
      : loadingConceptSourcesState(sourcesKey);
  const { sources, loading, loadError } = currentSourceState;
  const [formOpen, setFormOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getConceptSources(workspaceId, conceptId)
      .then((response) => {
        if (!cancelled) {
          setSourceState({
            key: sourcesKey,
            sources: response.sources,
            loading: false,
            loadError: null,
          });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setSourceState({
            ...loadingConceptSourcesState(sourcesKey),
            loading: false,
            loadError: errorMessage(error),
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, conceptId, sourcesKey]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setUploadError("Choose a file to upload.");
      return;
    }
    setUploading(true);
    setUploadError(null);
    try {
      const uploaded = await uploadSource(workspaceId, file, title);
      await linkSourceToConcept(workspaceId, uploaded.id, conceptId, "primary");
      const refreshed = await getConceptSources(workspaceId, conceptId);
      setSourceState((current) =>
        current.key === sourcesKey
          ? {
              ...current,
              sources: refreshed.sources,
              loading: false,
              loadError: null,
            }
          : current,
      );
      setFormOpen(false);
      setFile(null);
      setTitle("");
    } catch (error) {
      setUploadError(errorMessage(error));
    } finally {
      setUploading(false);
    }
  }

  return (
    <>
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-900">Sources</h3>
        <button
          type="button"
          onClick={() => {
            setFormOpen((current) => !current);
            setUploadError(null);
          }}
          className="rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
        >
          Add source
        </button>
      </div>

      {loading ? (
        <p className="mt-2 text-sm text-slate-500">Loading sources...</p>
      ) : null}
      {loadError ? (
        <p className="mt-2 text-sm text-red-600">{loadError}</p>
      ) : null}
      {!loading && !loadError && sources.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">No sources linked yet.</p>
      ) : null}
      {!loading && !loadError && sources.length > 0 ? (
        <ul className="mt-3 grid gap-2">
          {sources.map((source) => (
            <li
              key={`${source.source_id}-${source.relation}`}
              className="rounded-md border border-slate-200 p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-slate-800">
                  {source.title}
                </span>
                <Badge>{originLabel(source.origin)}</Badge>
                {source.origin === "user_upload" && source.ingestion_status ? (
                  <Badge>{statusLabel(source.ingestion_status)}</Badge>
                ) : null}
              </div>
              {source.url ? (
                <a
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 inline-block text-xs font-medium text-blue-700 hover:text-blue-800"
                >
                  Open source
                </a>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      {formOpen ? (
        <form
          onSubmit={handleSubmit}
          className="mt-3 grid gap-3 rounded-md border border-slate-200 p-3"
        >
          <label className="grid gap-1 text-xs font-medium text-slate-700">
            Source file
            <input
              type="file"
              accept="*"
              onChange={(event: ChangeEvent<HTMLInputElement>) => {
                setFile(event.target.files?.[0] ?? null);
                setUploadError(null);
              }}
              className="text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1 file:text-sm file:font-medium file:text-slate-700"
            />
          </label>
          <label className="grid gap-1 text-xs font-medium text-slate-700">
            Optional title
            <input
              type="text"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Defaults to filename"
              className="h-9 rounded-md border border-slate-200 px-3 text-sm font-normal text-slate-900 outline-none focus:border-blue-400"
            />
          </label>
          {uploadError ? (
            <p className="text-sm text-red-600">{uploadError}</p>
          ) : null}
          <button
            type="submit"
            disabled={uploading}
            className="h-9 rounded-md bg-blue-600 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-300"
          >
            {uploading ? "Uploading..." : "Upload & link"}
          </button>
        </form>
      ) : null}
    </>
  );
}

function originLabel(origin: string): string {
  if (origin === "user_upload") {
    return "upload";
  }
  if (origin === "research_agent") {
    return "research";
  }
  return origin.replaceAll("_", " ");
}

function statusLabel(status: string): string {
  if (status === "pending_parse") {
    return "Processing";
  }
  return status.replaceAll("_", " ");
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Source action failed.";
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

function Badge({
  children,
  icon: Icon,
}: {
  children: ReactNode;
  icon?: LucideIcon;
}) {
  return (
    <span className="inline-flex items-center gap-1 rounded border border-slate-200 bg-slate-50 px-2 py-1 font-medium text-slate-700">
      {Icon ? <Icon className="size-3.5" aria-hidden /> : null}
      {children}
    </span>
  );
}

// Mastery gets its own chip so the status reads clearly via both an icon and a
// title-cased label (never colour alone), per docs/FRONTEND.md.
const MASTERY_ICON: Record<MasteryStatus, LucideIcon> = {
  not_started: Circle,
  learning: BookOpen,
  needs_review: AlertCircle,
  mastered: CheckCircle2,
};

function MasteryBadge({ status }: { status: MasteryStatus }) {
  return <Badge icon={MASTERY_ICON[status]}>{titleCase(status)}</Badge>;
}
