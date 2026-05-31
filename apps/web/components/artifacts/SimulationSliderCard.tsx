"use client";

import { useMemo, useState } from "react";

import { ArtifactFrame } from "@/components/artifacts/ArtifactFrame";
import { ArtifactTextFallback } from "@/components/artifacts/ArtifactTextFallback";
import type {
  ArtifactEnvelope,
  SimulationParameter,
  SimulationPoint,
} from "@/lib/artifacts";
import {
  clampY,
  computeY,
  isKnownSimKind,
  type Coefficients,
} from "@/lib/simulations";

// Interactive but TRUSTED-TEMPLATE `simulation_slider` template (Phase 15e).
// The component renders <=3 sliders, an SVG line plot, and a predict-then-check
// prompt. On slider drag it live-evaluates the chosen sim_kind via the TRUSTED
// hardcoded compute registry in `lib/simulations.ts` (NO arbitrary JS / math
// eval), clamped to the backend `precomputed.y_bounds`. If the sim_kind is
// unknown or compute throws it degrades to the STATIC plot from
// `precomputed.at_defaults`; if `precomputed` itself is unusable it degrades to
// the envelope's `text_fallback` (mirroring every other template).

const PLOT_WIDTH = 320;
const PLOT_HEIGHT = 200;
const PLOT_PAD = 24;

function isValidParameter(value: unknown): value is SimulationParameter {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const p = value as Record<string, unknown>;
  return (
    typeof p.name === "string" &&
    typeof p.label === "string" &&
    Number.isFinite(p.min as number) &&
    Number.isFinite(p.max as number) &&
    Number.isFinite(p.default as number)
  );
}

function isValidPoint(value: unknown): value is SimulationPoint {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const p = value as Record<string, unknown>;
  return Number.isFinite(p.x as number) && Number.isFinite(p.y as number);
}

function buildPolyline(
  points: SimulationPoint[],
  xMin: number,
  xMax: number,
  yMin: number,
  yMax: number,
): string {
  const xSpan = xMax - xMin || 1;
  const ySpan = yMax - yMin || 1;
  const innerW = PLOT_WIDTH - PLOT_PAD * 2;
  const innerH = PLOT_HEIGHT - PLOT_PAD * 2;
  return points
    .map((point) => {
      const px = PLOT_PAD + ((point.x - xMin) / xSpan) * innerW;
      // SVG y grows downward, so invert.
      const py = PLOT_PAD + innerH - ((point.y - yMin) / ySpan) * innerH;
      return `${px.toFixed(2)},${py.toFixed(2)}`;
    })
    .join(" ");
}

export function SimulationSliderCard({
  envelope,
}: {
  envelope: ArtifactEnvelope;
}) {
  const data = envelope.data as unknown as
    | Record<string, unknown>
    | null
    | undefined;

  const simKind = data?.sim_kind;
  const rawParameters = data?.parameters;
  const precomputed = data?.precomputed as
    | { at_defaults?: unknown; y_bounds?: unknown }
    | null
    | undefined;
  const atDefaults = precomputed?.at_defaults;
  const yBounds = precomputed?.y_bounds as
    | { min?: unknown; max?: unknown }
    | null
    | undefined;

  const parameters = useMemo<SimulationParameter[]>(
    () =>
      Array.isArray(rawParameters) && rawParameters.every(isValidParameter)
        ? (rawParameters as SimulationParameter[])
        : [],
    [rawParameters],
  );

  const staticPoints = useMemo<SimulationPoint[]>(
    () =>
      Array.isArray(atDefaults) && atDefaults.every(isValidPoint)
        ? (atDefaults as SimulationPoint[])
        : [],
    [atDefaults],
  );

  const [coefficients, setCoefficients] = useState<Coefficients>(() =>
    Object.fromEntries(parameters.map((p) => [p.name, p.default])),
  );

  // The precomputed oracle must be usable for ANY render path (static or live).
  const boundsValid =
    typeof yBounds?.min === "number" &&
    typeof yBounds?.max === "number" &&
    Number.isFinite(yBounds.min) &&
    Number.isFinite(yBounds.max) &&
    yBounds.min <= yBounds.max;

  const yMin = boundsValid ? (yBounds!.min as number) : 0;
  const yMax = boundsValid ? (yBounds!.max as number) : 0;
  const xMin = staticPoints.length > 0 ? staticPoints[0].x : 0;
  const xMax =
    staticPoints.length > 0 ? staticPoints[staticPoints.length - 1].x : 0;

  // Live-evaluate at the SAME x grid as the backend oracle so the curve matches
  // `at_defaults` at the default coefficients. Degrade to the static points on
  // unknown sim_kind or any compute error.
  const livePoints = useMemo<SimulationPoint[]>(() => {
    if (!isKnownSimKind(simKind) || staticPoints.length === 0) {
      return staticPoints;
    }
    try {
      return staticPoints.map((point) => ({
        x: point.x,
        y: clampY(computeY(simKind, coefficients, point.x), yMin, yMax),
      }));
    } catch {
      return staticPoints;
    }
  }, [simKind, staticPoints, coefficients, yMin, yMax]);

  if (staticPoints.length === 0 || !boundsValid) {
    return <ArtifactTextFallback text={envelope.text_fallback} />;
  }

  const interactive = isKnownSimKind(simKind) && parameters.length > 0;
  const polyline = buildPolyline(livePoints, xMin, xMax, yMin, yMax);
  const xLabel = typeof data?.x_label === "string" ? data.x_label : "x";
  const yLabel = typeof data?.y_label === "string" ? data.y_label : "y";
  const prompt = typeof data?.prompt === "string" ? data.prompt : null;

  return (
    <ArtifactFrame
      title={envelope.title}
      caption={envelope.caption}
      testId="artifact-simulation-slider"
    >
      {prompt ? (
        <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm leading-6 text-slate-700 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-300">
          {prompt}
        </p>
      ) : null}

      <svg
        viewBox={`0 0 ${PLOT_WIDTH} ${PLOT_HEIGHT}`}
        role="img"
        aria-label={`Plot of ${yLabel} against ${xLabel}`}
        className="h-auto w-full rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900"
      >
        {/* Axes */}
        <line
          x1={PLOT_PAD}
          y1={PLOT_HEIGHT - PLOT_PAD}
          x2={PLOT_WIDTH - PLOT_PAD}
          y2={PLOT_HEIGHT - PLOT_PAD}
          className="stroke-slate-300 dark:stroke-slate-600"
          strokeWidth={1}
        />
        <line
          x1={PLOT_PAD}
          y1={PLOT_PAD}
          x2={PLOT_PAD}
          y2={PLOT_HEIGHT - PLOT_PAD}
          className="stroke-slate-300 dark:stroke-slate-600"
          strokeWidth={1}
        />
        <polyline
          data-testid="artifact-simulation-curve"
          points={polyline}
          fill="none"
          className="stroke-slate-900 dark:stroke-slate-100"
          strokeWidth={2}
        />
      </svg>

      <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        <span>{xLabel}</span>
        <span>{yLabel}</span>
      </div>

      {interactive ? (
        <div className="grid gap-3">
          {parameters.map((param) => (
            <label key={param.name} className="grid gap-1">
              <span className="flex items-baseline justify-between text-sm text-slate-700 dark:text-slate-300">
                <span className="font-medium">{param.label}</span>
                <span className="tabular-nums text-slate-500 dark:text-slate-400">
                  {(coefficients[param.name] ?? param.default).toFixed(2)}
                </span>
              </span>
              <input
                type="range"
                aria-label={param.label}
                min={param.min}
                max={param.max}
                step={param.step ?? ((param.max - param.min) / 100 || 0.01)}
                value={coefficients[param.name] ?? param.default}
                onChange={(event) =>
                  setCoefficients((prev) => ({
                    ...prev,
                    [param.name]: Number(event.target.value),
                  }))
                }
                className="w-full accent-slate-900 dark:accent-slate-100"
              />
            </label>
          ))}
        </div>
      ) : null}
    </ArtifactFrame>
  );
}
