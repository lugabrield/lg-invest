"""Testes do PortfolioAdequacyService (Sprint 26, Fase 5) — usa SQLite em
memória (fixture `db_session`), sem rede.

Nota: este módulo importa (via `PortfolioAdequacyService` ->
`TargetAllocationService`) `backend.app.services.fx_settings_service`, que
usa `from datetime import UTC` (Python 3.11+). Em sandbox com Python 3.10
este arquivo não coleciona — mesma limitação pré-existente de
`test_target_allocation_service.py`. Rodar no ambiente local (`.venv`
Python 3.11) para validar.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.app.infrastructure.database.models import Asset, Portfolio, Position, Price
from backend.app.schemas.portfolio_adequacy import (
    ADEQUACY_STATUS_INDETERMINATE,
    EVALUATED_DIMENSION_ASSET,
    EVALUATED_DIMENSION_CLASS,
)
from backend.app.services import target_allocation_settings_service as settings_svc
from backend.app.services.portfolio_adequacy_service import PortfolioAdequacyService
from backend.app.services.target_allocation_rule_service import TargetAllocationRuleService


@pytest.fixture(autouse=True)
def _isolated_settings_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_svc, "_SETTINGS_PATH", tmp_path / "app_settings.json")


def _seed_portfolio(db) -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.flush()

    etf = Asset(
        ticker="VOO", name="Vanguard S&P 500", asset_class="etf", country="US", currency="USD"
    )
    crypto = Asset(
        ticker="BTC-USD", name="Bitcoin", asset_class="crypto", country="US", currency="USD"
    )
    db.add_all([etf, crypto])
    db.flush()

    db.add_all(
        [
            Position(
                portfolio_id=portfolio.id,
                asset_id=etf.id,
                quantity=Decimal("10"),
                average_price=Decimal("400"),
                currency="USD",
                opened_at=date(2025, 1, 1),
            ),
            Position(
                portfolio_id=portfolio.id,
                asset_id=crypto.id,
                quantity=Decimal("0.1"),
                average_price=Decimal("40000"),
                currency="USD",
                opened_at=date(2025, 1, 1),
            ),
        ]
    )
    db.add(Price(asset_id=etf.id, date=date(2026, 6, 27), close=Decimal("450")))
    db.add(Price(asset_id=crypto.id, date=date(2026, 6, 27), close=Decimal("60000")))
    db.commit()
    return portfolio.id


def test_evaluate_ticker_unknown_asset_returns_none(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = PortfolioAdequacyService(db_session)
    assert service.evaluate_ticker("NOPE9.SA", portfolio_id) is None


def test_evaluate_ticker_no_rules_is_indeterminate(db_session):
    portfolio_id = _seed_portfolio(db_session)
    service = PortfolioAdequacyService(db_session)
    result = service.evaluate_ticker("VOO", portfolio_id)
    assert result is not None
    assert result.adequacy_status == ADEQUACY_STATUS_INDETERMINATE
    assert result.reason is not None


def test_evaluate_ticker_uses_asset_level_rule_when_present(db_session):
    portfolio_id = _seed_portfolio(db_session)
    TargetAllocationRuleService(db_session).set_rule(
        portfolio_id, dimension_type="asset", dimension_key="VOO", target_weight=Decimal("0.10")
    )

    result = PortfolioAdequacyService(db_session).evaluate_ticker("VOO", portfolio_id)

    assert result is not None
    assert result.evaluated_dimension == EVALUATED_DIMENSION_ASSET
    assert result.confidence == "alta"


def test_evaluate_ticker_falls_back_to_class_rule(db_session):
    portfolio_id = _seed_portfolio(db_session)
    TargetAllocationRuleService(db_session).set_rule(
        portfolio_id, dimension_type="class", dimension_key="crypto", target_weight=Decimal("0.05")
    )

    result = PortfolioAdequacyService(db_session).evaluate_ticker("BTC-USD", portfolio_id)

    assert result is not None
    assert result.evaluated_dimension == EVALUATED_DIMENSION_CLASS
    assert result.confidence == "média"
    assert result.class_current_weight is not None


def test_evaluate_ticker_out_of_scope_asset_class(db_session):
    portfolio_id = _seed_portfolio(db_session)
    asset = Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    db_session.add(asset)
    db_session.commit()

    result = PortfolioAdequacyService(db_session).evaluate_ticker("WEGE3.SA", portfolio_id)

    assert result is not None
    assert "stock" in result.reason
