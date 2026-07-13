"""Testes da estabilidade de DY histórico — puro (Sprint 26, Fase 4)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.income_real_estate.stability import dy_stability
from backend.app.schemas.income_real_estate import (
    DY_STABILITY_INDETERMINATE,
    DY_STABILITY_STABLE,
    DY_STABILITY_UNSTABLE,
)


def test_empty_series_is_indeterminate():
    classification, average, reason = dy_stability([])
    assert classification == DY_STABILITY_INDETERMINATE
    assert average is None
    assert reason is not None


def test_single_value_is_indeterminate_insufficient_history():
    classification, average, reason = dy_stability([Decimal("0.08")])
    assert classification == DY_STABILITY_INDETERMINATE
    assert average is None
    assert "histórico insuficiente" in reason


def test_none_and_zero_values_are_filtered_out():
    classification, average, reason = dy_stability(
        [None, Decimal("0"), Decimal("0.08")]  # type: ignore[list-item]
    )
    assert classification == DY_STABILITY_INDETERMINATE
    assert average is None
    assert reason is not None


def test_consistent_series_is_stable():
    series = [Decimal("0.08"), Decimal("0.081"), Decimal("0.079"), Decimal("0.08")]
    classification, average, reason = dy_stability(series)
    assert classification == DY_STABILITY_STABLE
    assert average is not None
    assert Decimal("0.079") < average < Decimal("0.081")
    assert reason is None


def test_volatile_series_is_unstable():
    series = [Decimal("0.02"), Decimal("0.18"), Decimal("0.03"), Decimal("0.15")]
    classification, average, reason = dy_stability(series)
    assert classification == DY_STABILITY_UNSTABLE
    assert average is not None


def test_average_reflects_full_positive_series():
    series = [Decimal("0.06"), Decimal("0.06"), Decimal("0.18")]
    _, average, _ = dy_stability(series)
    assert average == Decimal("0.1")
