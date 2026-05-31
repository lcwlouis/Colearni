import { ArtifactFrame } from "@/components/artifacts/ArtifactFrame";
import { ArtifactTextFallback } from "@/components/artifacts/ArtifactTextFallback";
import type { ArtifactEnvelope, WorkedExampleStep } from "@/lib/artifacts";

// Read-only `worked_example` template: an ordered list of labelled steps with
// an optional final answer. Guards against missing/empty steps by degrading to
// the envelope's `text_fallback`.

function isValidStep(value: unknown): value is WorkedExampleStep {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const step = value as Record<string, unknown>;
  return typeof step.label === "string" && typeof step.detail === "string";
}

export function WorkedExampleCard({
  envelope,
}: {
  envelope: ArtifactEnvelope;
}) {
  const data = envelope.data as unknown as
    | Record<string, unknown>
    | null
    | undefined;
  const steps = data?.steps;

  if (
    !Array.isArray(steps) ||
    steps.length === 0 ||
    !steps.every(isValidStep)
  ) {
    return <ArtifactTextFallback text={envelope.text_fallback} />;
  }

  const finalAnswer = data?.final_answer;

  return (
    <ArtifactFrame
      title={envelope.title}
      caption={envelope.caption}
      testId="artifact-worked-example"
    >
      <ol className="grid gap-3">
        {steps.map((step, index) => (
          <li key={index} className="grid min-w-0 gap-1">
            <div className="flex min-w-0 items-baseline gap-2">
              <span className="shrink-0 text-xs font-semibold tabular-nums text-slate-400 dark:text-slate-500">
                {index + 1}.
              </span>
              <span className="min-w-0 wrap-break-word text-sm font-medium text-slate-900 dark:text-slate-100">
                {step.label}
              </span>
            </div>
            <p className="min-w-0 whitespace-pre-wrap wrap-break-word pl-5 text-sm leading-6 text-slate-700 dark:text-slate-300">
              {step.detail}
            </p>
          </li>
        ))}
      </ol>

      {typeof finalAnswer === "string" && finalAnswer.trim().length > 0 ? (
        <div className="grid gap-1 border-t border-slate-200 pt-3 dark:border-slate-700">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Final answer
          </span>
          <p className="min-w-0 whitespace-pre-wrap wrap-break-word text-sm font-medium leading-6 text-slate-900 dark:text-slate-100">
            {finalAnswer}
          </p>
        </div>
      ) : null}
    </ArtifactFrame>
  );
}
