import { ArtifactFrame } from "@/components/artifacts/ArtifactFrame";
import { ArtifactTextFallback } from "@/components/artifacts/ArtifactTextFallback";
import type { ArtifactEnvelope, TimelineEvent } from "@/lib/artifacts";

// Read-only `timeline` template: an ordered, vertical list of events. Each
// event has a `label`, a free-form `when` marker, and an optional `note`.
// Guards against missing/empty events by degrading to the envelope's
// `text_fallback`.

function isValidEvent(value: unknown): value is TimelineEvent {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const event = value as Record<string, unknown>;
  return typeof event.label === "string" && typeof event.when === "string";
}

export function TimelineCard({ envelope }: { envelope: ArtifactEnvelope }) {
  const data = envelope.data as unknown as
    | Record<string, unknown>
    | null
    | undefined;
  const events = data?.events;

  if (
    !Array.isArray(events) ||
    events.length === 0 ||
    !events.every(isValidEvent)
  ) {
    return <ArtifactTextFallback text={envelope.text_fallback} />;
  }

  return (
    <ArtifactFrame
      title={envelope.title}
      caption={envelope.caption}
      testId="artifact-timeline"
    >
      <ol className="grid gap-4 border-l border-slate-200 pl-4 dark:border-slate-700">
        {events.map((event, index) => (
          <li key={index} className="relative grid min-w-0 gap-1">
            <span
              aria-hidden
              className="absolute -left-[1.3125rem] top-1 h-2.5 w-2.5 rounded-full border-2 border-white bg-slate-400 dark:border-slate-900 dark:bg-slate-500"
            />
            <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {event.when}
            </span>
            <span className="min-w-0 wrap-break-word text-sm font-medium text-slate-900 dark:text-slate-100">
              {event.label}
            </span>
            {typeof event.note === "string" && event.note.trim().length > 0 ? (
              <p className="min-w-0 whitespace-pre-wrap wrap-break-word text-sm leading-6 text-slate-700 dark:text-slate-300">
                {event.note}
              </p>
            ) : null}
          </li>
        ))}
      </ol>
    </ArtifactFrame>
  );
}
