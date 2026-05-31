import { describe, expect, test } from "vitest";

import {
  clampY,
  computeY,
  isKnownSimKind,
  SIMULATION_PARAM_NAMES,
} from "@/lib/simulations";

// Parity fixtures: these `at_defaults` were produced by the BACKEND oracle
// (backend/app/services/simulations.py -> precompute_simulation) at the default
// coefficients over x in [0, 10]. The client compute functions MUST reproduce
// them within tolerance, proving the formulas are equivalent on both sides.
const BACKEND_ORACLE = {
  linear: {
    coefficients: { m: 2, b: 1 },
    at_defaults: [
      { x: 0, y: 1 },
      { x: 2.5, y: 6 },
      { x: 5, y: 11 },
      { x: 7.5, y: 16 },
      { x: 10, y: 21 },
    ],
    y_bounds: { min: 1, max: 21 },
  },
  quadratic: {
    coefficients: { a: 1, b: -2, c: 3 },
    at_defaults: [
      { x: 0, y: 3 },
      { x: 2.5, y: 4.25 },
      { x: 5, y: 18 },
      { x: 7.5, y: 44.25 },
      { x: 10, y: 83 },
    ],
    y_bounds: { min: 3, max: 83 },
  },
  supply_demand: {
    coefficients: { a: 100, b: 5 },
    at_defaults: [
      { x: 0, y: 100 },
      { x: 2.5, y: 87.5 },
      { x: 5, y: 75 },
      { x: 7.5, y: 62.5 },
      { x: 10, y: 50 },
    ],
    y_bounds: { min: 50, max: 100 },
  },
} as const;

const TOLERANCE = 1e-9;

describe("simulation compute parity with backend oracle", () => {
  for (const [simKind, fixture] of Object.entries(BACKEND_ORACLE)) {
    test(`${simKind} client live-eval matches backend at_defaults`, () => {
      for (const point of fixture.at_defaults) {
        const y = computeY(simKind, fixture.coefficients, point.x);
        expect(y).toBeCloseTo(point.y, 9);
      }
    });
  }

  test("clampY keeps live-eval inside y_bounds", () => {
    const { min, max } = BACKEND_ORACLE.linear.y_bounds;
    expect(clampY(1000, min, max)).toBe(max);
    expect(clampY(-1000, min, max)).toBe(min);
    expect(clampY(NaN, min, max)).toBe(min);
    expect(clampY(11, min, max)).toBe(11);
  });

  test("unknown sim_kind throws and is not a known kind", () => {
    expect(isKnownSimKind("mystery")).toBe(false);
    expect(() => computeY("mystery", {}, 1)).toThrow();
  });

  test("expected param names match the closed contract", () => {
    expect(SIMULATION_PARAM_NAMES.linear).toEqual(["m", "b"]);
    expect(SIMULATION_PARAM_NAMES.quadratic).toEqual(["a", "b", "c"]);
    expect(SIMULATION_PARAM_NAMES.exponential).toEqual(["a", "k"]);
    expect(SIMULATION_PARAM_NAMES.supply_demand).toEqual(["a", "b"]);
  });

  test("exponential matches a * exp(k*x) within tolerance", () => {
    const y = computeY("exponential", { a: 2, k: 0.5 }, 4);
    expect(y).toBeCloseTo(2 * Math.exp(2), 9);
    expect(Math.abs(y - 2 * Math.exp(2))).toBeLessThan(TOLERANCE);
  });
});
