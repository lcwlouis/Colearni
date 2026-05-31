import type { ReactNode } from "react";

// Shared outer surface for artifact templates. This IS the single card — per
// docs/FRONTEND.md "do not put cards inside cards", template content must NOT
// introduce nested card surfaces inside this frame.

export function ArtifactFrame({
  title,
  caption,
  children,
  testId,
}: {
  title?: string | null;
  caption?: string | null;
  children: ReactNode;
  testId?: string;
}) {
  const safeTitle =
    typeof title === "string" && title.trim().length > 0 ? title : "Artifact";

  return (
    <section
      data-testid={testId}
      className="grid min-w-0 gap-3 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900"
    >
      <header className="grid gap-1">
        <h3 className="min-w-0 wrap-break-word text-base font-semibold text-slate-900 dark:text-slate-100">
          {safeTitle}
        </h3>
        {typeof caption === "string" && caption.trim().length > 0 ? (
          <p className="min-w-0 wrap-break-word text-sm text-slate-500 dark:text-slate-400">
            {caption}
          </p>
        ) : null}
      </header>
      {children}
    </section>
  );
}
