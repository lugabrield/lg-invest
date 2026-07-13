"""Testes dos múltiplos normalizados pelo próprio histórico (Sprint 26, Fase 2)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from backend.app.engines.valuation_v2.multiples import normalized_multiples_fair_value
from backend.app.schemas.fundamentals import FundamentalSnapshotResult


def _snap(period_end, **kwargs) -> FundamentalSnapshotResult:
    base = {
        "ticker": "WEGE3.SA",
        "period_end": period_end,
        "source": "yahoo",
        "collected_at": datetime(2025, 1, 1),
    }
    base.update(kwargs)
    return FundamentalSnapshotResult(**base)


def test_normalized_multiples_uses_average_pe_times_current_eps():
    history = [
        _snap(date(2022, 12, 31), pe_ratio=Decimal("10")),
        _snap(date(2023, 12, 31), pe_ratio=Decimal("14")),
    ]
    value, reason = normalized_multiples_fair_value(history, Decimal("5"), None)
    assert reason is None
    # média P/L = 12; 12 x EPS 5 = 60
    assert value == Decimal("60")


def test_normalized_multiples_uses_average_pb_times_current_bvps():
    history = [
        _snap(date(2022, 12, 31), pb_ratio=Decimal("1.0")),
        _snap(date(2023, 12, 31), pb_ratio=Decimal("2.0")),
    ]
    value, reason = normalized_multiples_fair_value(history, None, Decimal("20"))
    assert reason is None
    # média P/VP = 1.5; 1.5 x VPA 20 = 30
    assert value == Decimal("30")


def test_normalized_multiples_averages_pe_and_pb_estimates_when_both_available():
    history = [
        _snap(date(2022, 12, 31), pe_ratio=Decimal("10"), pb_ratio=Decimal("1.0")),
        _snap(date(2023, 12, 31), pe_ratio=Decimal("14"), pb_ratio=Decimal("2.0")),
    ]
    value, reason = normalized_multiples_fair_value(history, Decimal("5"), Decimal("20"))
    assert reason is None
    # estimativa P/L = 60, estimativa P/VP = 30 -> média = 45
    assert value == Decimal("45")


def test_normalized_multiples_none_with_less_than_min_periods():
    history = [_snap(date(2023, 12, 31), pe_ratio=Decimal("14"))]
    value, reason = normalized_multiples_fair_value(history, Decimal("5"), None)
    assert value is None
    assert "histórico insuficiente" in reason


def test_normalized_multiples_none_without_current_eps_or_bvps():
    history = [
        _snap(date(2022, 12, 31), pe_ratio=Decimal("10")),
        _snap(date(2023, 12, 31), pe_ratio=Decimal("14")),
    ]
    value, reason = normalized_multiples_fair_value(history, None, None)
    assert value is None
    assert reason is not None


def test_normalized_multiples_ignores_non_positive_multiples_in_history():
    history = [
        _snap(date(2021, 12, 31), pe_ratio=Decimal("-5")),  # descartado
        _snap(date(2022, 12, 31), pe_ratio=Decimal("10")),
        _snap(date(2023, 12, 31), pe_ratio=Decimal("14")),
    ]
    value, reason = normalized_multiples_fair_value(history, Decimal("5"), None)
    assert reason is None
    assert value == Decimal("60")  # média continua sendo (10+14)/2, sem o -5
