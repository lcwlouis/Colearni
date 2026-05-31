"""Unit tests for the trusted simulation compute functions (Phase 15e)."""

from __future__ import annotations

import math

import pytest

from backend.app.services.simulations import (
    SIMULATION_MAX_ABS_Y,
    compute_y,
    precompute_simulation,
    sample_xs,
)


def test_linear_compute():
    assert compute_y("linear", {"m": 2.0, "b": 1.0}, 3.0) == pytest.approx(7.0)


def test_quadratic_compute():
    # a*x^2 + b*x + c = 1*4 + (-2)*2 + 3 = 3
    assert compute_y("quadratic", {"a": 1.0, "b": -2.0, "c": 3.0}, 2.0) == pytest.approx(3.0)


def test_exponential_compute():
    assert compute_y("exponential", {"a": 2.0, "k": 1.0}, 1.0) == pytest.approx(2.0 * math.e)


def test_supply_demand_compute():
    # Linear demand: a - b*x = 100 - 5*4 = 80
    assert compute_y("supply_demand", {"a": 100.0, "b": 5.0}, 4.0) == pytest.approx(80.0)


def test_unknown_sim_kind_raises():
    with pytest.raises(KeyError):
        compute_y("mystery", {}, 1.0)


def test_sample_xs_spans_range_inclusive():
    xs = sample_xs(0.0, 10.0, count=11)
    assert xs[0] == 0.0
    assert xs[-1] == 10.0
    assert len(xs) == 11


def test_precompute_matches_compute_function():
    coefficients = {"m": 2.0, "b": 1.0}
    result = precompute_simulation("linear", coefficients, x_min=0.0, x_max=10.0)
    for point in result["at_defaults"]:
        assert point["y"] == pytest.approx(compute_y("linear", coefficients, point["x"]))
    ys = [point["y"] for point in result["at_defaults"]]
    assert result["y_bounds"]["min"] == pytest.approx(min(ys))
    assert result["y_bounds"]["max"] == pytest.approx(max(ys))


def test_precompute_rejects_unbounded_y():
    # A steep exponential blows past SIMULATION_MAX_ABS_Y over 0..10.
    with pytest.raises(ValueError):
        precompute_simulation("exponential", {"a": 1.0, "k": 10.0}, x_min=0.0, x_max=10.0)


def test_max_abs_y_constant_is_sane():
    assert SIMULATION_MAX_ABS_Y > 0
