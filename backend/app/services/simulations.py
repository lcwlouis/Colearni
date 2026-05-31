"""Trusted simulation compute functions for the ``simulation_slider`` artifact.

This module is the BACKEND oracle for the interactive ``simulation_slider``
template (see docs/REBUILD_PLAN.md Phase 15e). It is a CLOSED ENUM of vetted,
hardcoded compute functions — there is NO arbitrary code/formula evaluation.

Each ``sim_kind`` maps to:
- a fixed tuple of expected coefficient parameter names (``SIMULATION_PARAM_NAMES``)
- a pure ``(coefficients, x) -> y`` compute function (``SIMULATION_COMPUTE``)

The frontend ships byte-for-byte equivalent compute functions in
``apps/web/lib/simulations.ts``; the parity is unit-tested on both sides so the
client live-eval matches the ``precomputed.at_defaults`` oracle within tolerance.

Coefficient -> param-name mapping per sim_kind:
- ``linear``:        y = m*x + b                  (m = slope, b = intercept)
- ``quadratic``:     y = a*x^2 + b*x + c          (a, b, c)
- ``exponential``:   y = a * exp(k*x)             (a = scale, k = rate)
- ``supply_demand``: y = a - b*x                  (linear demand curve:
                                                   a = choke quantity at price 0,
                                                   b = price sensitivity, x = price)
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

# Number of evenly spaced sample points used to build ``at_defaults`` and to
# derive ``y_bounds``. Kept small: it is a render hint + validation oracle.
SIMULATION_SAMPLE_COUNT = 25

# A sample whose magnitude exceeds this is treated as "unbounded" and rejected.
# Keeps exponential / steep curves from producing runaway render hints.
SIMULATION_MAX_ABS_Y = 1e9

# Default x-axis sampling range used when the payload omits ``x_range``.
DEFAULT_SIM_X_MIN = 0.0
DEFAULT_SIM_X_MAX = 10.0

Coefficients = dict[str, float]
SimCompute = Callable[[Coefficients, float], float]


def _linear(c: Coefficients, x: float) -> float:
    return c["m"] * x + c["b"]


def _quadratic(c: Coefficients, x: float) -> float:
    return c["a"] * x * x + c["b"] * x + c["c"]


def _exponential(c: Coefficients, x: float) -> float:
    return c["a"] * math.exp(c["k"] * x)


def _supply_demand(c: Coefficients, x: float) -> float:
    # Linear demand curve: quantity demanded as a function of price ``x``.
    # a = quantity at price 0 (choke intercept), b = price sensitivity.
    return c["a"] - c["b"] * x


# The closed sim_kind enum -> trusted compute function registry.
SIMULATION_COMPUTE: dict[str, SimCompute] = {
    "linear": _linear,
    "quadratic": _quadratic,
    "exponential": _exponential,
    "supply_demand": _supply_demand,
}

# Expected coefficient parameter names per sim_kind (the closed contract the
# schema validates the emitted ``parameters`` against).
SIMULATION_PARAM_NAMES: dict[str, tuple[str, ...]] = {
    "linear": ("m", "b"),
    "quadratic": ("a", "b", "c"),
    "exponential": ("a", "k"),
    "supply_demand": ("a", "b"),
}

# The closed set of supported sim_kinds (single source of truth).
SIMULATION_KINDS: tuple[str, ...] = tuple(SIMULATION_COMPUTE.keys())


def compute_y(sim_kind: str, coefficients: Coefficients, x: float) -> float:
    """Evaluate the trusted compute function for ``sim_kind`` at ``x``."""
    fn = SIMULATION_COMPUTE.get(sim_kind)
    if fn is None:
        raise KeyError(f"unknown sim_kind: {sim_kind!r}")
    return fn(coefficients, x)


def sample_xs(x_min: float, x_max: float, count: int = SIMULATION_SAMPLE_COUNT) -> list[float]:
    """Evenly spaced x sample positions across ``[x_min, x_max]`` inclusive."""
    if count < 2:
        count = 2
    span = x_max - x_min
    return [x_min + span * i / (count - 1) for i in range(count)]


def precompute_simulation(
    sim_kind: str,
    coefficients: Coefficients,
    *,
    x_min: float,
    x_max: float,
    count: int = SIMULATION_SAMPLE_COUNT,
) -> dict:
    """Compute the ``precomputed`` oracle (``at_defaults`` + ``y_bounds``).

    Samples the trusted compute function over the x-range and rejects any
    payload whose derived ``y`` is non-finite (NaN/inf) or unbounded. This is
    the backend validation oracle AND the render hint shipped to the client.
    """
    xs = sample_xs(x_min, x_max, count)
    at_defaults: list[dict[str, float]] = []
    ys: list[float] = []
    for x in xs:
        y = compute_y(sim_kind, coefficients, x)
        if not math.isfinite(y):
            raise ValueError(f"simulation_slider '{sim_kind}' produced a non-finite y at x={x}")
        if abs(y) > SIMULATION_MAX_ABS_Y:
            raise ValueError(
                f"simulation_slider '{sim_kind}' produced an unbounded y "
                f"({y}) at x={x} (limit {SIMULATION_MAX_ABS_Y})"
            )
        at_defaults.append({"x": x, "y": y})
        ys.append(y)
    return {"at_defaults": at_defaults, "y_bounds": {"min": min(ys), "max": max(ys)}}


def expected_param_names(sim_kind: str) -> Sequence[str]:
    """Expected coefficient names for ``sim_kind`` (empty if unknown)."""
    return SIMULATION_PARAM_NAMES.get(sim_kind, ())
