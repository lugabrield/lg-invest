"""Schemas do Income Engine (Sprint 24, Fase 7)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class MonthlyPointView(BaseModel):
    year: int
    month: int
    amount_total: Decimal

    model_config = {"from_attributes": True}


class PortfolioIncomeTrendView(BaseModel):
    ttm_total: Decimal
    prior_ttm_total: Decimal
    growth_pct: Decimal | None = None
    monthly_series: list[MonthlyPointView]
    projected_next_12_months: Decimal
    months_with_data_ttm: int
    months_with_data_prior_ttm: int
    reason: str

    model_config = {"from_attributes": True}


class TickerIncomeRowView(BaseModel):
    ticker: str
    ttm_income: Decimal
    cost_basis: Decimal | None = None
    yield_on_cost: Decimal | None = None

    model_config = {"from_attributes": True}


class TickerIncomeBreakdownView(BaseModel):
    rows: list[TickerIncomeRowView]
    concentration_hhi: Decimal | None = None
    portfolio_yield_on_cost: Decimal | None = None
    excluded_tickers_without_position: list[str]
    reason: str

    model_config = {"from_attributes": True}


class IncomeAnalysisResultView(BaseModel):
    model_version: str
    trend: PortfolioIncomeTrendView
    breakdown: TickerIncomeBreakdownView
    reasons: list[str]
    warnings: list[str]

    model_config = {"from_attributes": True}
