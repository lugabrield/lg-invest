"""Testes do DataQualityService (Sprint 22) — banco SQLite em memória.

Cobre os dois ajustes desta sprint na fronteira banco->engine:
1. `is_manual` do ativo tem prioridade sobre a origem do preço ao
   classificar `price_status` (Tesouro Direto nunca deve aparecer como
   "ausente"/"estimado").
2. Para FIIs, a cobertura de fundamentos é calculada só sobre o
   subconjunto priorizado (`pb_ratio`, `dividend_yield`), não sobre os
   28 campos completos usados para ações.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.infrastructure.database.base import Base
from backend.app.infrastructure.database.models import Asset, Portfolio, Position, Price
from backend.app.infrastructure.database.models.fundamental_snapshot import FundamentalSnapshot
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.services.data_quality_service import DataQualityService


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


def _make_asset(db_session, **kwargs) -> Asset:
    defaults = dict(ticker="WEGE3.SA", name="X", asset_class="stock", country="BR", currency="BRL")
    defaults.update(kwargs)
    return AssetRepository(db_session).create(Asset(**defaults))


# --- is_manual tem prioridade sobre a origem do preço ----------------------


def test_manual_asset_without_any_price_row_is_classified_as_manual(db_session):
    asset = _make_asset(
        db_session,
        ticker="TESOURO-IPCA-2050",
        name="Tesouro IPCA+ 2050",
        asset_class="bond",
        is_manual=True,
    )
    dq = DataQualityService(db_session).evaluate_ticker(
        asset.ticker, asset.id, asset.asset_class, is_manual=asset.is_manual
    )
    assert dq.price_status == "manual"
    assert not any("ausente" in issue for issue in dq.issues)


def test_manual_asset_with_yahoo_source_price_is_still_manual(db_session):
    asset = _make_asset(
        db_session,
        ticker="TESOURO-IPCA-2050",
        name="Tesouro IPCA+ 2050",
        asset_class="bond",
        is_manual=True,
    )
    db_session.add(Price(asset_id=asset.id, date=date(2026, 6, 27), close=Decimal("1.15")))
    db_session.commit()

    dq = DataQualityService(db_session).evaluate_ticker(
        asset.ticker, asset.id, asset.asset_class, is_manual=True
    )
    assert dq.price_status == "manual"


def test_non_manual_asset_without_price_is_estimado(db_session):
    asset = _make_asset(db_session, ticker="ITUB4.SA", asset_class="stock")
    dq = DataQualityService(db_session).evaluate_ticker(
        asset.ticker, asset.id, asset.asset_class, is_manual=False
    )
    assert dq.price_status == "estimado"


# --- FII: cobertura de fundamentos só sobre pb_ratio/dividend_yield --------


def test_fii_fundamentals_coverage_uses_priority_fields_only(db_session):
    asset = _make_asset(
        db_session, ticker="BTLG11.SA", name="BTG Pactual Logistica", asset_class="fii"
    )
    FundamentalsRepository(db_session).create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2026, 6, 30),
            source="yahoo",
            pb_ratio=Decimal("1.05"),
            dividend_yield=Decimal("0.095"),
            # Campos não priorizados para FII — não devem contar na cobertura.
            roe=Decimal("0.28"),
            net_margin=Decimal("0.18"),
        )
    )
    dq = DataQualityService(db_session).evaluate_ticker(
        asset.ticker, asset.id, asset.asset_class, is_manual=False
    )
    assert dq.fundamentals_fields_total == 2
    assert dq.fundamentals_fields_available == 2
    assert dq.fundamentals_status == "completo"


def test_fii_fundamentals_coverage_ignores_non_priority_fields_when_missing_priority_ones(
    db_session,
):
    asset = _make_asset(
        db_session, ticker="BTLG11.SA", name="BTG Pactual Logistica", asset_class="fii"
    )
    FundamentalsRepository(db_session).create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2026, 6, 30),
            source="yahoo",
            roe=Decimal("0.28"),
            net_margin=Decimal("0.18"),
        )
    )
    dq = DataQualityService(db_session).evaluate_ticker(
        asset.ticker, asset.id, asset.asset_class, is_manual=False
    )
    assert dq.fundamentals_fields_total == 2
    assert dq.fundamentals_fields_available == 0


def test_stock_fundamentals_coverage_uses_full_field_list(db_session):
    asset = _make_asset(db_session, ticker="WEGE3.SA", asset_class="stock")
    FundamentalsRepository(db_session).create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2026, 6, 30),
            source="yahoo",
            roe=Decimal("0.28"),
            net_margin=Decimal("0.18"),
        )
    )
    dq = DataQualityService(db_session).evaluate_ticker(
        asset.ticker, asset.id, asset.asset_class, is_manual=False
    )
    assert dq.fundamentals_fields_total == 28


# --- evaluate_portfolio: is_manual propagado a partir do Asset -------------


def test_evaluate_portfolio_propagates_is_manual_from_asset(db_session):
    portfolio = Portfolio(name="Carteira teste", base_currency="BRL")
    db_session.add(portfolio)
    db_session.flush()

    tesouro = Asset(
        ticker="TESOURO-IPCA-2050",
        name="Tesouro IPCA+ 2050",
        asset_class="bond",
        country="BR",
        currency="BRL",
        is_manual=True,
    )
    db_session.add(tesouro)
    db_session.flush()
    db_session.add(
        Position(
            portfolio_id=portfolio.id,
            asset_id=tesouro.id,
            quantity=Decimal("5000"),
            average_price=Decimal("1.10"),
            currency="BRL",
            opened_at=date(2025, 1, 1),
        )
    )
    db_session.commit()

    summary = DataQualityService(db_session).evaluate_portfolio(portfolio.id)
    tesouro_dq = next(a for a in summary.per_asset if a.ticker == "TESOURO-IPCA-2050")
    assert tesouro_dq.price_status == "manual"
    assert "TESOURO-IPCA-2050" in summary.assets_manual
