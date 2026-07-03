"""Testes do portfolio_diagnostics_service (wiring DB -> view -> engine).

Fronteira fina: só garante que o serviço monta o DashboardView e chama
o engine corretamente. As regras em si são testadas sem banco em
`test_portfolio_diagnostics_engine.py`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.models import Asset, Portfolio, Position, Price
from backend.app.services.portfolio_diagnostics_service import get_portfolio_diagnostics


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_portfolio(db) -> int:
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.flush()

    wege = Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    tesouro = Asset(
        ticker="TESOURO-IPCA-2050",
        name="Tesouro IPCA+ 2050",
        asset_class="bond",
        country="BR",
        currency="BRL",
    )
    db.add_all([wege, tesouro])
    db.flush()

    db.add_all(
        [
            Position(
                portfolio_id=portfolio.id,
                asset_id=wege.id,
                quantity=Decimal("100"),
                average_price=Decimal("38"),
                currency="BRL",
                opened_at=date(2025, 1, 1),
            ),
            Position(
                portfolio_id=portfolio.id,
                asset_id=tesouro.id,
                quantity=Decimal("100"),
                average_price=Decimal("1.10"),
                currency="BRL",
                opened_at=date(2025, 1, 1),
            ),
        ]
    )
    db.add(Price(asset_id=wege.id, date=date(2026, 6, 27), close=Decimal("40")))
    # TESOURO sem Price -> vira "estimated" no DashboardView.
    db.commit()
    return portfolio.id


def test_get_portfolio_diagnostics_returns_insights(db_session):
    portfolio_id = _seed_portfolio(db_session)
    diagnostics = get_portfolio_diagnostics(db_session, portfolio_id, exchange_rate=Decimal("5"))

    codes = {i.code for i in diagnostics.insights}
    assert "concentration_single_asset" in codes
    assert "manual_or_estimated_prices" in codes  # TESOURO sem preço


def test_get_portfolio_diagnostics_empty_portfolio(db_session):
    portfolio = Portfolio(name="Vazia", base_currency="BRL")
    db_session.add(portfolio)
    db_session.commit()

    diagnostics = get_portfolio_diagnostics(db_session, portfolio.id, exchange_rate=Decimal("5"))
    assert diagnostics.insights == []
