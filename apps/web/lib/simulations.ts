// Trusted, hardcoded frontend compute functions for the `simulation_slider`
// artifact (Phase 15e). This is the CLIENT mirror of
// `backend/app/services/simulations.py`: a CLOSED ENUM of vetted
// `(coefficients, x) -> y` functions. There is NO arbitrary JS, NO formula
// strings, and NO browser-side math evaluation. The formulas MUST stay
// byte-for-byte equivalent to the backend; parity is unit-tested against the
// backend `precomputed.at_defaults` oracle.

export type SimKind = "linear" | "quadratic" | "exponential" | "supply_demand";

export type Coefficients = Record<string, number>;

// Expected coefficient names per sim_kind (mirrors SIMULATION_PARAM_NAMES).
export const SIMULATION_PARAM_NAMES: Record<SimKind, readonly string[]> = {
  linear: ["m", "b"],
  quadratic: ["a", "b", "c"],
  exponential: ["a", "k"],
  supply_demand: ["a", "b"],
};

// The closed sim_kind -> trusted compute function registry.
export const SIMULATION_COMPUTE: Record<
  SimKind,
  (c: Coefficients, x: number) => number
> = {
  // y = m*x + b
  linear: (c, x) => c.m * x + c.b,
  // y = a*x^2 + b*x + c
  quadratic: (c, x) => c.a * x * x + c.b * x + c.c,
  // y = a * exp(k*x)
  exponential: (c, x) => c.a * Math.exp(c.k * x),
  // Linear demand curve: y = a - b*x (x = price, a = choke quantity).
  supply_demand: (c, x) => c.a - c.b * x,
};

export function isKnownSimKind(value: unknown): value is SimKind {
  return typeof value === "string" && value in SIMULATION_COMPUTE;
}

/**
 * Evaluate the trusted compute function for `simKind` at `x`.
 * Throws if `simKind` is not part of the closed enum.
 */
export function computeY(
  simKind: string,
  coefficients: Coefficients,
  x: number,
): number {
  const fn = SIMULATION_COMPUTE[simKind as SimKind];
  if (!fn) {
    throw new Error(`unknown sim_kind: ${simKind}`);
  }
  return fn(coefficients, x);
}

/** Clamp `y` into `[min, max]`, mapping non-finite results to `min`. */
export function clampY(y: number, min: number, max: number): number {
  if (!Number.isFinite(y)) {
    return min;
  }
  return Math.min(max, Math.max(min, y));
}
