// The universal safe degrade target for the artifact registry. Every unknown
// kind, invalid payload, or thrown render error ends up here, mirroring the
// Mermaid `catch -> textContent` philosophy in markdown-text.tsx.

const GENERIC_FALLBACK =
  "This artifact could not be displayed. No fallback text was provided.";

export function ArtifactTextFallback({ text }: { text?: string | null }) {
  const safeText =
    typeof text === "string" && text.trim().length > 0 ? text : GENERIC_FALLBACK;

  return (
    <p
      data-testid="artifact-text-fallback"
      className="min-w-0 whitespace-pre-wrap wrap-break-word text-sm leading-6 text-slate-700 dark:text-slate-300"
    >
      {safeText}
    </p>
  );
}
