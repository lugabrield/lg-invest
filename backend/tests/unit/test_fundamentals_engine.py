"""Testes do Fundamentals Engine (Sprint 14) — puro, sem banco/rede."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from backend.app.engines.fundamentals.cagr import compute_cagr
from backend.app.engines.fundamentals.engine import FundamentalsEngine
from backend.app.schemas.fundamentals import FundamentalSnapshotResult


def _snapshot(period_end, **kwargs) -> FundamentalSnapshotResult:
    base = {
        "ticker": "WEGE3.SA",
        "period_end": period_end,
        "source": "yahoo",
        "collected_at": datetime(2026, 7, 2, 12, 0, 0),
    }
    base.update(kwargs)
    return FundamentalSnapshotResult(**base)


# --- compute_cagr (função pura) -------------------------------------------


def test_cagr_insufficient_history():
    cagr, reason = compute_cagr([(date(2026, 1, 1), Decimal("100"))])
    assert cagr is None
    assert "insuficiente" in reason


def test_cagr_basic_growth():
    series = [
        (date(2024, 12, 31), Decimal("1000")),
        (date(2025, 12, 31), Decimal("1100")),
    ]
    cagr, reason = compute_cagr(series)
    assert reason is None
    assert float(cagr) == pytest.approx(0.10, abs=0.005)


def test_cagr_non_positive_start_value():
    series = [
        (date(2024, 12, 31), Decimal("-50")),
        (date(2025, 12, 31), Decimal("100")),
    ]
    cagr, reason = compute_cagr(series)
    assert cagr is None
    assert "não positivo" in reason


def test_cagr_zero_time_span():
    series = [
        (date(2025, 12, 31), Decimal("100")),
        (date(2025, 12, 31), Decimal("110")),
    ]
    cagr, reason = compute_cagr(series)
    assert cagr is None
    assert "tempo insuficiente" in reason


# --- FundamentalsEngine.analyze --------------------------------------------


def test_engine_no_snapshots_returns_low_confidence():
    engine = FundamentalsEngine()
    result = engine.analyze("WEGE3.SA", [])
    assert result.periods_used == 0
    assert result.confidence == "baixa"
    assert result.reason is not None
    assert result.revenue_cagr is None


def test_engine_single_snapshot_all_cagr_none():
    engine = FundamentalsEngine()
    snapshots = [_snapshot(date(2026, 6, 30), revenue=Decimal("1000"))]
    result = engine.analyze("WEGE3.SA", snapshots)
    assert result.periods_used == 1
    assert result.revenue_cagr is None
    assert result.confidence == "baixa"


def test_engine_full_history_high_confidence():
    engine = FundamentalsEngine()
    snapshots = [
        _snapshot(
            date(2023, 12, 31),
            revenue=Decimal("800"),
            net_income=Decimal("100"),
            ebitda=Decimal("200"),
            free_cash_flow=Decimal("80"),
            net_margin=Decimal("0.10"),
        ),
        _snapshot(
            date(2025, 12, 31),
            revenue=Decimal("968"),
            net_income=Decimal("121"),
            ebitda=Decimal("242"),
            free_cash_flow=Decimal("96.8"),
            net_margin=Decimal("0.15"),
        ),
    ]
    result = engine.analyze("WEGE3.SA", snapshots)
    assert result.periods_used == 2
    assert result.confidence == "alta"
    assert result.revenue_cagr is not None
    assert result.net_income_cagr is not None
    assert result.ebitda_cagr is not None
    assert result.fcf_cagr is not None
    assert result.margin_trend == "melhorando"


def test_engine_partial_data_is_medium_confidence():
    engine = FundamentalsEngine()
    snapshots = [
        _snapshot(date(2023, 12, 31), revenue=Decimal("800")),
        _snapshot(date(2025, 12, 31), revenue=Decimal("968")),
    ]
    result = engine.analyze("WEGE3.SA", snapshots)
    assert result.confidence == "média"
    assert result.revenue_cagr is not None
    assert result.net_income_cagr is None
    assert result.net_income_cagr_reason is not None


def test_engine_margin_trend_declining():
    engine = FundamentalsEngine()
    snapshots = [
        _snapshot(date(2023, 12, 31), net_margin=Decimal("0.20")),
        _snapshot(date(2025, 12, 31), net_margin=Decimal("0.10")),
    ]
    result = engine.analyze("WEGE3.SA", snapshots)
    assert result.margin_trend == "piorando"


def test_engine_margin_trend_stable_within_threshold():
    engine = FundamentalsEngine()
    snapshots = [
        _snapshot(date(2023, 12, 31), net_margin=Decimal("0.20")),
        _snapshot(date(2025, 12, 31), net_margin=Decimal("0.205")),
    ]
    result = engine.analyze("WEGE3.SA", snapshots)
    assert result.margin_trend == "estável"
