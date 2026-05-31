"use client";

import { useEffect, useRef, useState } from "react";

import { ArtifactRenderer } from "@/components/artifacts/ArtifactRenderer";
import { PinToggle } from "@/components/PinToggle";
import { listArtifacts, streamBuildArtifact } from "@/lib/api";
import type { ArtifactKind, ArtifactRead } from "@/lib/artifacts";

type GenerateStatus = "retrieving" | "generating";

interface ArtifactsPanelProps {
  workspaceId: string;
  trailId: string;
  conceptId: string;
  onBack: () => void;
  // Opt-in auto-start: when the tutor's suggest_artifact CTA opens this panel it
  // passes the chosen kind so we kick off that build once on mount. The concept
  // action row opens the panel with this null, so nothing auto-starts there.
  initialGenerateKind?: ArtifactKind | null;
}

// The two on-demand builders surfaced in the concept panel. Adding a new kind to
// the registry later is enough to extend this list; everything else dispatches
// through ArtifactRenderer.
const GENERATE_ACTIONS: { kind: ArtifactKind; label: string }[] = [
  { kind: "worked_example", label: "Generate worked example" },
  { kind: "comparison_card", label: "Generate comparison" },
];

// Display labels for every artifact kind. The concept action row only surfaces
// the two GENERATE_ACTIONS buttons, but the tutor's suggest_artifact CTA can
// auto-start any kind, so the in-progress status needs labels for all of them.
const ARTIFACT_KIND_LABELS: Record<ArtifactKind, string> = {
  worked_example: "worked example",
  comparison_card: "comparison card",
  timeline: "timeline",
  mini_graph: "mini graph",
  simulation_slider: "simulation",
};

export function ArtifactsPanel({
  workspaceId,
  trailId,
  conceptId,
  onBack,
  initialGenerateKind = null,
}: ArtifactsPanelProps) {
  const [artifacts, setArtifacts] = useState<ArtifactRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [generatingKind, setGeneratingKind] = useState<ArtifactKind | null>(
    null,
  );
  const [generateStatus, setGenerateStatus] = useState<GenerateStatus | null>(
    null,
  );
  const [generateError, setGenerateError] = useState("");
  // Guards the opt-in auto-start so the suggested build kicks off exactly once,
  // even across React StrictMode double-invokes or re-renders.
  const autoStartedRef = useRef(false);

  useEffect(() => {
    // The panel is concept-keyed (remounts per concept), so loading/error start
    // at their initial values on every (re)mount; no synchronous reset needed.
    let cancelled = false;

    listArtifacts(workspaceId, trailId, conceptId)
      .then((response) => {
        if (cancelled) return;
        setArtifacts(response.artifacts);
        setLoading(false);
      })
      .catch((exc) => {
        if (cancelled) return;
        setError(
          exc instanceof Error ? exc.message : "Could not load artifacts",
        );
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [workspaceId, trailId, conceptId]);

  useEffect(() => {
    // Opt-in auto-start: the learner clicked the tutor's suggest_artifact CTA,
    // which opened this panel with the chosen kind, so we start that build once.
    // Bare panel opens (concept action row) pass null and never auto-start.
    if (autoStartedRef.current || !initialGenerateKind) {
      return;
    }
    autoStartedRef.current = true;
    void handleGenerate(initialGenerateKind);
    // handleGenerate is a stable local closure; we intentionally fire only on
    // the initial kind so re-renders never re-trigger a build.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialGenerateKind]);

  async function handleGenerate(kind: ArtifactKind) {
    if (generatingKind !== null) {
      return;
    }
    setGeneratingKind(kind);
    setGenerateStatus("retrieving");
    setGenerateError("");
    try {
      await streamBuildArtifact(
        workspaceId,
        trailId,
        { kind, conceptId },
        {
          onStatus: (status) => setGenerateStatus(status),
          onDone: (artifact) => {
            // Prepend the fresh artifact; dedupe in case the backend deduped to
            // an already-listed one (recent-artifact hit returns it unchanged).
            setArtifacts((current) => [
              artifact,
              ...current.filter((item) => item.id !== artifact.id),
            ]);
          },
          onError: (message) => setGenerateError(message),
        },
      );
    } catch (exc) {
      setGenerateError(
        (current) =>
          current ||
          (exc instanceof Error ? exc.message : "Could not generate artifact"),
      );
    } finally {
      setGeneratingKind(null);
      setGenerateStatus(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">
          Saved artifacts
        </h3>
        <button
          type="button"
          onClick={onBack}
          className="text-xs text-slate-500 hover:text-slate-800"
        >
          Back
        </button>
      </div>

      <p className="text-xs text-slate-500">
        Generate a worked example or a comparison card grounded in this
        concept&apos;s sources. Saved artifacts appear here.
      </p>

      <div className="flex flex-wrap gap-2">
        {GENERATE_ACTIONS.map(({ kind, label }) => (
          <button
            key={kind}
            type="button"
            disabled={generatingKind !== null}
            onClick={() => handleGenerate(kind)}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {label}
          </button>
        ))}
      </div>

      {generatingKind ? (
        <ArtifactGenerationStatus
          kind={generatingKind}
          status={generateStatus}
        />
      ) : null}

      {generateError ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {generateError}
        </div>
      ) : null}

      {loading ? (
        <p className="py-8 text-center text-sm text-slate-500">
          Loading artifacts...
        </p>
      ) : error ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      ) : artifacts.length === 0 ? (
        <p className="rounded-md border border-dashed border-slate-300 bg-slate-50 p-4 text-center text-sm text-slate-500">
          No artifacts yet. Generate a worked example or comparison to get
          started.
        </p>
      ) : (
        <div className="grid gap-3">
          {artifacts.map((artifact) => (
            <div key={artifact.id} className="space-y-2">
              <div className="flex justify-end">
                <PinToggle
                  workspaceId={workspaceId}
                  trailId={trailId}
                  itemType="artifact"
                  itemId={artifact.id}
                />
              </div>
              <ArtifactRenderer envelope={artifact.payload} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ArtifactGenerationStatus({
  kind,
  status,
}: {
  kind: ArtifactKind;
  status: GenerateStatus | null;
}) {
  const label = ARTIFACT_KIND_LABELS[kind] ?? kind.replace(/_/g, " ");
  const detail =
    status === "retrieving"
      ? "Retrieving sources to ground the artifact..."
      : "Generating the artifact from this concept...";

  return (
    <div
      className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-900"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 h-3 w-3 animate-pulse rounded-full bg-blue-500" />
        <div>
          <p className="font-semibold">Preparing your {label}...</p>
          <p className="mt-1 text-blue-800">{detail}</p>
        </div>
      </div>
    </div>
  );
}
