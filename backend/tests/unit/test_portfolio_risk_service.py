"""Testes do PortfolioRiskService (Sprint 24, Fase 6) — wiring DB -> Portfolio
Risk Engine."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.infrastructure.database.models import Asset, Portfolio, Position, Price
from backend.app.services import simulation_assumptions_service as assumptions_svc
from backend.app.services.portfolio_risk_service import PortfolioRiskService


@pytest.fixture(autouse=True)
def _isolated_settings_file(tmp_path, monkeypatch):
    settings_path = tmp_path / "app_settings.json"
    monkeypatch.setattr(assumptions_svc, "_SETTINGS_PATH", settings_path)
    yield settings_path


def _seed_portfolio(db) -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.flush()

    stock = Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    crypto = Asset(
        ticker="BTC-USD", name="Bitcoin", asset_class="crypto", country="US", currency="USD"
    )
    db.add_all([stock, crypto])
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
                asset_id=crypto.id,
                quantity=Decimal("0.01"),
                average_price=Decimal("60000"),
                currency="USD",
                opened_at=date(2025, 1, 1),
            ),
        ]
    )
    db.add(Price(asset_id=stock.id, date=date(2026, 6, 27), close=Decimal("40")))
    db.add(Price(asset_id=crypto.id, date=date(2026, 6, 27), close=Decimal("63000")))
    db.commit()
    return portfolio.id


def test_build_input_reflects_concentration_weights_and_signals(db_session):
    portfolio_id = _seed_portfolio(db_session)
    data = PortfolioRiskService(db_session).build_input(portfolio_id)

    assert data.concentration_hhi > Decimal("0")
    assert set(data.class_weights.keys()) == {"stock", "crypto"}
    assert data.international_weight > Decimal("0")
    tickers = {s.ticker for s in data.asset_risk_signals}
    assert tickers == {"WEGE3.SA", "BTC-USD"}


def test_build_input_uses_crypto_policy_classification_from_risk_engine_v1(db_session):
    portfolio_id = _seed_portfolio(db_session)
    data = PortfolioRiskService(db_session).build_input(portfolio_id)
    btc_signal = next(s for s in data.asset_risk_signals if s.ticker == "BTC-USD")
    # Risk Engine v1 classifica cripto como "alto" por política, mesmo sem
    # snapshot de fundamentos (Sprint 21).
    assert btc_signal.classification == "alto"


def test_build_input_uses_investment_policy_default_risk_tolerance(db_session):
    portfolio_id = _seed_portfolio(db_session)
    data = PortfolioRiskService(db_session).build_input(portfolio_id)
    assert data.declared_risk_tolerance == "moderado-alto"


def test_evaluate_end_to_end_without_simulation_leaves_drawdown_unavailable(db_session):
    portfolio_id = _seed_portfolio(db_session)
    result = PortfolioRiskService(db_session).evaluate(portfolio_id)
    assert result.model_version == "portfolio_risk_v1"
    drawdown = next(f for f in result.factors if f.name == "risco_de_cauda")
    assert drawdown.available is False
    assert result.overall_classification in ("baixo", "moderado", "moderado-alto", "alto")


def test_evaluate_with_probability_of_loss_includes_drawdown_factor(db_session):
    portfolio_id = _seed_portfolio(db_session)
    result = PortfolioRiskService(db_session).evaluate(
        portfolio_id, probability_of_loss=Decimal("0.12")
    )
    drawdown = next(f for f in result.factors if f.name == "risco_de_cauda")
    assert drawdown.available is True
