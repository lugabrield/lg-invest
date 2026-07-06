"""Testes do IncomeAnalysisService (Sprint 24, Fase 7) — wiring DB -> Income
Engine."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.infrastructure.database.models import (
    Asset,
    IncomeEvent,
    IncomeMonthlySummary,
    Portfolio,
    Position,
    Price,
)
from backend.app.services.income_analysis_service import IncomeAnalysisService

_REF = date(2026, 6, 30)


def _seed_portfolio_with_income(db) -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.flush()

    stock = Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    db.add(stock)
    db.flush()

    db.add(
        Position(
            portfolio_id=portfolio.id,
            asset_id=stock.id,
            quantity=Decimal("100"),
            average_price=Decimal("38"),
            currency="BRL",
            opened_at=date(2025, 1, 1),
        )
    )
    db.add(Price(asset_id=stock.id, date=date(2026, 6, 27), close=Decimal("40")))

    for i in range(12):
        year, month = _REF.year, _REF.month - i
        if month <= 0:
            month += 12
            year -= 1
        db.add(
            IncomeMonthlySummary(
                portfolio_id=portfolio.id,
                wallet_name="Carteira (B3)",
                year=year,
                month=month,
                amount_total=Decimal("100"),
                currency="BRL",
                source="dividendos_me:income_monthly:brasil",
                status="recebido",
            )
        )

    db.add(
        IncomeEvent(
            portfolio_id=portfolio.id,
            asset_id=stock.id,
            ticker="WEGE3.SA",
            source="dividendos_me:income_calendar",
            event_type="dividendo",
            status="recebido",
            payment_date=date(2026, 3, 15),
            amount_total=Decimal("50"),
            currency="BRL",
        )
    )
    db.commit()
    return portfolio.id


def test_build_input_converts_monthly_summaries_and_events(db_session):
    portfolio_id = _seed_portfolio_with_income(db_session)
    data = IncomeAnalysisService(db_session).build_input(portfolio_id, reference_date=_REF)
    assert len(data.monthly_totals) == 12
    assert len(data.ticker_events) == 1
    assert data.position_cost_basis["WEGE3.SA"] == Decimal("3800")


def test_evaluate_end_to_end_returns_coherent_result(db_session):
    portfolio_id = _seed_portfolio_with_income(db_session)
    result = IncomeAnalysisService(db_session).evaluate(portfolio_id, reference_date=_REF)
    assert result.model_version == "income_v1"
    assert result.trend.ttm_total == Decimal("1200")
    assert result.breakdown.rows[0].ticker == "WEGE3.SA"
    assert result.breakdown.rows[0].yield_on_cost is not None


def test_evaluate_empty_portfolio_has_no_income_without_error(db_session):
    empty = Portfolio(name="Carteira vazia", base_currency="BRL")
    db_session.add(empty)
    db_session.commit()

    result = IncomeAnalysisService(db_session).evaluate(empty.id, reference_date=_REF)
    assert result.trend.ttm_total == Decimal("0")
    assert result.breakdown.rows == []
