"""Testes do dashboard_view_service (conversão cambial + fallback de preço).

Cobre exatamente o que a Portfolio Engine v1 deliberadamente não faz:
conversão USD->BRL e fallback de preço para ativos sem cotação. Usa
banco SQLite em memória, sem rede (mesmo padrão dos testes de regressão).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.models import Asset, Portfolio, Position, Price
from backend.app.services.dashboard_view_service import build_dashboard_view


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


def _seed_multi_currency_portfolio(db) -> int:
    """WEGE3 (BRL, com preço), VOO (USD, com preço) e TESOURO (BRL, sem preço)."""
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db.add(portfolio)
    db.flush()

    wege = Asset(ticker="WEGE3.SA", name="WEG", asset_class="stock", country="BR", currency="BRL")
    voo = Asset(
        ticker="VOO", name="Vanguard S&P 500", asset_class="etf", country="US", currency="USD"
    )
    tesouro = Asset(
        ticker="TESOURO-IPCA-2050",
        name="Tesouro IPCA+ 2050",
        asset_class="bond",
        country="BR",
        currency="BRL",
    )
    db.add_all([wege, voo, tesouro])
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
                asset_id=voo.id,
                quantity=Decimal("10"),
                average_price=Decimal("400"),
                currency="USD",
                opened_at=date(2025, 1, 1),
            ),
            Position(
                portfolio_id=portfolio.id,
                asset_id=tesouro.id,
                quantity=Decimal("5000"),
                average_price=Decimal("1.10"),
                currency="BRL",
                opened_at=date(2025, 1, 1),
            ),
        ]
    )
    db.add_all(
        [
            Price(asset_id=wege.id, date=date(2026, 6, 27), close=Decimal("40")),
            Price(asset_id=voo.id, date=date(2026, 6, 27), close=Decimal("420")),
            # Sem Price para tesouro -> deve cair no fallback average_price.
        ]
    )
    db.commit()
    return portfolio.id


def test_currency_conversion_totals(db_session):
    portfolio_id = _seed_multi_currency_portfolio(db_session)
    view = build_dashboard_view(db_session, portfolio_id, exchange_rate=Decimal("5"))

    # WEGE3: 100*40 = 4000 BRL ; TESOURO fallback: 5000*1.10 = 5500 BRL
    assert view.total_brl == Decimal("9500")
    # VOO: 10*420 = 4200 USD
    assert view.total_usd == Decimal("4200")
    # Convertido: 9500 + 4200*5 = 30500
    assert view.total_converted_brl == Decimal("30500")
    assert view.exchange_rate == Decimal("5")
    assert view.is_multi_currency is True


def test_estimated_price_fallback_flagged(db_session):
    portfolio_id = _seed_multi_currency_portfolio(db_session)
    view = build_dashboard_view(db_session, portfolio_id, exchange_rate=Decimal("5"))

    assert "TESOURO-IPCA-2050" in view.estimated_price_tickers
    tesouro_pos = next(p for p in view.positions if p.ticker == "TESOURO-IPCA-2050")
    assert tesouro_pos.is_price_estimated is True
    assert tesouro_pos.current_price == Decimal("1.10")  # average_price usado como fallback

    wege_pos = next(p for p in view.positions if p.ticker == "WEGE3.SA")
    assert wege_pos.is_price_estimated is False

    # Nenhum ticker deve sobrar como "sem preço" depois do fallback.
    assert view.unpriced_tickers == []


def test_currency_exposure_weights_use_converted_values(db_session):
    portfolio_id = _seed_multi_currency_portfolio(db_session)
    view = build_dashboard_view(db_session, portfolio_id, exchange_rate=Decimal("5"))

    exposure_by_currency = {c.currency: c for c in view.currency_exposure}
    assert exposure_by_currency["BRL"].value_brl == Decimal("9500")
    assert exposure_by_currency["USD"].value_brl == Decimal("21000")  # 4200 * 5
    total_weight = sum(c.weight for c in view.currency_exposure)
    assert total_weight == pytest.approx(Decimal("1"))


def test_group_labels(db_session):
    portfolio_id = _seed_multi_currency_portfolio(db_session)
    view = build_dashboard_view(db_session, portfolio_id, exchange_rate=Decimal("5"))

    labels = {p.ticker: p.group_label for p in view.positions}
    assert labels["WEGE3.SA"] == "Ações BR"
    assert labels["VOO"] == "ETFs"
    assert labels["TESOURO-IPCA-2050"] == "Renda Fixa"


def test_largest_position_uses_converted_value(db_session):
    portfolio_id = _seed_multi_currency_portfolio(db_session)
    view = build_dashboard_view(db_session, portfolio_id, exchange_rate=Decimal("5"))

    # VOO convertido = 4200*5 = 21000, maior que TESOURO (5500) e WEGE (4000).
    assert view.largest_position_ticker == "VOO"


def test_single_currency_portfolio_matches_nominal_total(db_session):
    portfolio = Portfolio(name="BRL only", base_currency="BRL")
    db_session.add(portfolio)
    db_session.flush()

    asset = Asset(ticker="ITUB4.SA", name="Itau", asset_class="stock", country="BR", currency="BRL")
    db_session.add(asset)
    db_session.flush()
    db_session.add(
        Position(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("200"),
            average_price=Decimal("28"),
            currency="BRL",
            opened_at=date(2025, 1, 1),
        )
    )
    db_session.add(Price(asset_id=asset.id, date=date(2026, 6, 27), close=Decimal("30")))
    db_session.commit()

    view = build_dashboard_view(db_session, portfolio.id, exchange_rate=Decimal("5"))
    assert view.total_converted_brl == Decimal("6000")
    assert view.total_usd == Decimal("0")
    assert view.is_multi_currency is False
    assert view.estimated_price_tickers == []


def test_price_source_yahoo_by_default(db_session):
    """Preço coletado sem passar `source` explicitamente vira 'yahoo' (Sprint 11)."""
    portfolio_id = _seed_multi_currency_portfolio(db_session)
    view = build_dashboard_view(db_session, portfolio_id, exchange_rate=Decimal("5"))

    wege_pos = next(p for p in view.positions if p.ticker == "WEGE3.SA")
    assert wege_pos.price_source == "yahoo"
    assert wege_pos.price_updated_at is not None
    assert view.manual_price_tickers == []


def test_price_source_estimated_when_no_price_at_all(db_session):
    portfolio_id = _seed_multi_currency_portfolio(db_session)
    view = build_dashboard_view(db_session, portfolio_id, exchange_rate=Decimal("5"))

    tesouro_pos = next(p for p in view.positions if p.ticker == "TESOURO-IPCA-2050")
    assert tesouro_pos.price_source == "estimated"
    assert tesouro_pos.price_updated_at is None


def test_price_source_manual_when_flagged(db_session):
    portfolio_id = _seed_multi_currency_portfolio(db_session)

    tesouro = db_session.query(Asset).filter(Asset.ticker == "TESOURO-IPCA-2050").one()
    db_session.add(
        Price(asset_id=tesouro.id, date=date(2026, 6, 28), close=Decimal("1.15"), source="manual")
    )
    db_session.commit()

    view = build_dashboard_view(db_session, portfolio_id, exchange_rate=Decimal("5"))
    tesouro_pos = next(p for p in view.positions if p.ticker == "TESOURO-IPCA-2050")
    assert tesouro_pos.price_source == "manual"
    assert tesouro_pos.is_price_estimated is False
    assert "TESOURO-IPCA-2050" in view.manual_price_tickers
    assert "TESOURO-IPCA-2050" not in view.estimated_price_tickers


def test_total_return_pct_and_cost(db_session):
    portfolio_id = _seed_multi_currency_portfolio(db_session)
    view = build_dashboard_view(db_session, portfolio_id, exchange_rate=Decimal("5"))

    # Custo: WEGE 100*38=3800 ; VOO 10*400*5=20000 ; TESOURO 5000*1.10=5500 (fallback == custo)
    assert view.total_cost_brl == Decimal("29300")
    assert view.total_return_pct == pytest.approx(
        (view.total_converted_brl - view.total_cost_brl) / view.total_cost_brl
    )
