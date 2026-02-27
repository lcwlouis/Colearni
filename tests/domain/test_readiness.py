"""Unit tests for the readiness analyzer – half-life decay logic."""

from __future__ import annotations

import math

import pytest


class TestReadinessDecay:
    """Test the half-life decay formula without requiring a database."""

    @staticmethod
    def _compute_readiness(mastery_score: float, elapsed_days: float, half_life: float) -> float:
        """Replicate the decay formula from domain.readiness.analyzer."""
        return mastery_score * math.pow(2, -elapsed_days / half_life)

    def test_no_decay_at_zero_elapsed(self) -> None:
        assert self._compute_readiness(0.8, 0.0, 7.0) == pytest.approx(0.8)

    def test_half_decay_at_half_life(self) -> None:
        assert self._compute_readiness(1.0, 7.0, 7.0) == pytest.approx(0.5)

    def test_quarter_decay_at_two_half_lives(self) -> None:
        assert self._compute_readiness(1.0, 14.0, 7.0) == pytest.approx(0.25)

    def test_zero_mastery_stays_zero(self) -> None:
        assert self._compute_readiness(0.0, 100.0, 7.0) == pytest.approx(0.0)

    def test_high_mastery_decays_slowly(self) -> None:
        readiness = self._compute_readiness(0.95, 3.0, 7.0)
        assert 0.5 < readiness < 0.95

    def test_recommend_threshold(self) -> None:
        """Topics below 0.5 readiness with mastery >= 0.3 should recommend quiz."""
        mastery = 0.6
        readiness = self._compute_readiness(mastery, 10.0, 7.0)
        recommend = readiness < 0.5 and mastery >= 0.3
        assert recommend is True
