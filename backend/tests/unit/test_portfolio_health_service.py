"""Testes do PortfolioHealthService (Sprint 24, Fase 8) — wiring dos 4
serviços existentes (PortfolioService, PortfolioRiskService,
TargetAllocationService, IncomeAnalysisService, DataQualityService) ->
Portfolio Health Score."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.infrastructure.database.models import Asset, Portfolio, Position, Price
from backend.app.services.portfolio_health_service import PortfolioHealthService


def _seed_portfolio(db) -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.flush()

    stock = Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    bond = Asset(
        ticker="TESOURO-IPCA",
        name="Tesouro IPCA+",
        asset_class="bond",
        country="BR",
        currency="BRL",
    )
    db.add_all([stock, bond])
    db.flush()

    db.add_all(
        [
            Position(
                portfolio_id=portfolio.id,
                asset_id=stock.id,
                quantity=Decimal("100"),
                average_price=Decimal("38"),
                currency="BRL",
                opened_at=date(2025, 1, 1),
            ),
            Position(
                portfolio_id=portfolio.id,
                asset_id=bond.id,
                quantity=Decimal("1"),
                average_price=Decimal("6000"),
                currency="BRL",
                opened_at=date(2025, 1, 1),
            ),
        ]
    )
    db.add(Price(asset_id=stock.id, date=date(2026, 6, 27), close=Decimal("40")))
    db.add(Price(asset_id=bond.id, date=date(2026, 6, 27), close=Decimal("6200")))
    db.commit()
    return portfolio.id


def test_build_input_reflects_diversification_and_defaults(db_session):
    portfolio_id = _seed_portfolio(db_session)
    data = PortfolioHealthService(db_session).build_input(portfolio_id)
    assert data.effective_number_of_assets is not None
    assert data.declared_risk_tolerance == "moderado-alto"
    # Sem regras de alocação-alvo configuradas nesta carteira.
    assert data.allocation_alignment is None
    # Sem eventos de renda nesta carteira.
    assert data.income_growth_pct is None


def test_evaluate_end_to_end_returns_coherent_result(db_session):
    portfolio_id = _seed_portfolio(db_session)
    result = PortfolioHealthService(db_session).evaluate(portfolio_id)
    assert result.model_version == "portfolio_health_v1"
    assert result.overall_classification in (
        "crítica",
        "atenção",
        "boa",
        "excelente",
        "indeterminado",
    )
    diversification = next(f for f in result.factors if f.name == "diversificação")
    assert diversification.available is True


def test_evaluate_empty_portfolio_does_not_error(db_session):
    portfolio = Portfolio(name="Carteira vazia", base_currency="BRL")
    db_session.add(portfolio)
    db_session.commit()
    result = PortfolioHealthService(db_session).evaluate(portfolio.id)
    assert result.model_version == "portfolio_health_v1"
