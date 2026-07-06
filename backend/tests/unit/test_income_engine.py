"""Testes do Income Engine (Sprint 24, Fase 7) — engine pura, sem banco."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.engines.income.engine import analyze_income
from backend.app.engines.income.inputs import (
    IncomeConfig,
    IncomeEngineInput,
    MonthlyIncomeTotal,
    TickerIncomeEvent,
)

_REF = date(2026, 6, 30)


def _monthly_flat(amount: Decimal, months: int = 24, ref: date = _REF) -> tuple:
    entries = []
    year, month = ref.year, ref.month
    for _ in range(months):
        entries.append(MonthlyIncomeTotal(year=year, month=month, amount_total=amount))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return tuple(entries)


def test_ttm_total_sums_last_12_months_only():
    monthly = _monthly_flat(Decimal("100"), months=24)
    data = IncomeEngineInput(reference_date=_REF, monthly_totals=monthly)
    result = analyze_income(data)
    assert result.trend.ttm_total == Decimal("1200")
    assert result.trend.prior_ttm_total == Decimal("1200")


def test_growth_pct_none_without_prior_period_data():
    monthly = _monthly_flat(Decimal("100"), months=6)
    data = IncomeEngineInput(reference_date=_REF, monthly_totals=monthly)
    result = analyze_income(data)
    assert result.trend.growth_pct is None
    assert any("crescimento de renda" in w for w in result.warnings)


def test_growth_pct_computed_when_prior_period_available():
    entries = []
    year, month = _REF.year, _REF.month
    for i in range(24):
        amount = Decimal("110") if i < 12 else Decimal("100")
        entries.append(MonthlyIncomeTotal(year=year, month=month, amount_total=amount))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    data = IncomeEngineInput(reference_date=_REF, monthly_totals=tuple(entries))
    result = analyze_income(data)
    assert result.trend.growth_pct is not None
    assert result.trend.ttm_total == Decimal("1320")
    assert result.trend.prior_ttm_total == Decimal("1200")


def test_zero_history_yields_zero_projection_with_warning():
    data = IncomeEngineInput(reference_date=_REF, monthly_totals=())
    result = analyze_income(data)
    assert result.trend.ttm_total == Decimal("0")
    assert result.trend.projected_next_12_months == Decimal("0")
    assert any("sem histórico" in w for w in result.warnings)


def test_monthly_series_respects_lookback_window():
    monthly = _monthly_flat(Decimal("50"), months=30)
    data = IncomeEngineInput(reference_date=_REF, monthly_totals=monthly)
    result = analyze_income(data, IncomeConfig(months_lookback=12))
    assert len(result.trend.monthly_series) == 12


def test_ticker_breakdown_computes_yield_on_cost():
    events = (
        TickerIncomeEvent("WEGE3.SA", date(2026, 3, 1), Decimal("40")),
        TickerIncomeEvent("WEGE3.SA", date(2025, 9, 1), Decimal("40")),
    )
    data = IncomeEngineInput(
        reference_date=_REF,
        ticker_events=events,
        position_cost_basis={"WEGE3.SA": Decimal("4000")},
    )
    result = analyze_income(data)
    row = result.breakdown.rows[0]
    assert row.ttm_income == Decimal("80")
    assert row.yield_on_cost == Decimal("0.02")
    assert result.breakdown.portfolio_yield_on_cost == Decimal("0.02")


def test_ticker_without_cost_basis_has_none_yield():
    events = (TickerIncomeEvent("XYZ3.SA", date(2026, 3, 1), Decimal("10")),)
    data = IncomeEngineInput(
        reference_date=_REF, ticker_events=events, position_cost_basis={"XYZ3.SA": Decimal("0")}
    )
    result = analyze_income(data)
    row = result.breakdown.rows[0]
    assert row.yield_on_cost is None


def test_income_events_without_matching_position_are_excluded_from_yield_but_counted_in_concentration():
    events = (
        TickerIncomeEvent("WEGE3.SA", date(2026, 3, 1), Decimal("50")),
        TickerIncomeEvent("SOLD3.SA", date(2026, 2, 1), Decimal("50")),
    )
    data = IncomeEngineInput(
        reference_date=_REF, ticker_events=events, position_cost_basis={"WEGE3.SA": Decimal("2000")}
    )
    result = analyze_income(data)
    assert "SOLD3.SA" in result.breakdown.excluded_tickers_without_position
    assert result.breakdown.concentration_hhi == Decimal("0.5")


def test_concentration_hhi_is_one_for_single_income_source():
    events = (TickerIncomeEvent("WEGE3.SA", date(2026, 3, 1), Decimal("100")),)
    data = IncomeEngineInput(reference_date=_REF, ticker_events=events)
    result = analyze_income(data)
    assert result.breakdown.concentration_hhi == Decimal("1")


def test_no_ticker_events_leaves_breakdown_empty_without_error():
    data = IncomeEngineInput(reference_date=_REF)
    result = analyze_income(data)
    assert result.breakdown.rows == []
    assert result.breakdown.concentration_hhi is None
    assert result.breakdown.portfolio_yield_on_cost is None


def test_monthly_trend_and_ticker_breakdown_never_summed_together():
    result = analyze_income(
        IncomeEngineInput(
            reference_date=_REF,
            monthly_totals=_monthly_flat(Decimal("100"), months=12),
            ticker_events=(TickerIncomeEvent("WEGE3.SA", date(2026, 3, 1), Decimal("999")),),
        )
    )
    assert any("nunca são somadas" in r for r in result.reasons)


def test_model_version_is_stable():
    result = analyze_income(IncomeEngineInput(reference_date=_REF))
    assert result.model_version == "income_v1"
