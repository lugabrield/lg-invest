"""Testes do ValuationServiceV2 (Sprint 26, Fase 2) — usa SQLite em memória
(fixture `db_session`), sem rede.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.database.models.fundamental_snapshot import FundamentalSnapshot
from backend.app.infrastructure.database.models.price import Price
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.infrastructure.repositories.price_repository import PriceRepository
from backend.app.schemas.valuation_v2 import (
    INSUFFICIENT_DATA_MESSAGE,
    VALUATION_STATUS_INDETERMINATE,
)
from backend.app.services.valuation_v2_service import ValuationServiceV2


def _make_asset(db_session, ticker="WEGE3.SA", asset_class="stock", currency="BRL") -> Asset:
    return AssetRepository(db_session).create(
        Asset(ticker=ticker, name="X", asset_class=asset_class, country="BR", currency=currency)
    )


def test_evaluate_ticker_unknown_asset_returns_none(db_session):
    service = ValuationServiceV2(db_session)
    assert service.evaluate_ticker("NOPE9.SA") is None


def test_evaluate_ticker_no_snapshot_returns_insufficient_data_message(db_session):
    _make_asset(db_session)
    service = ValuationServiceV2(db_session)
    result = service.evaluate_ticker("WEGE3.SA")
    assert result is not None
    assert result.valuation_status == VALUATION_STATUS_INDETERMINATE
    assert result.reason == INSUFFICIENT_DATA_MESSAGE


def test_evaluate_ticker_out_of_scope_asset_class(db_session):
    _make_asset(db_session, ticker="BTLG11.SA", asset_class="fii")
    service = ValuationServiceV2(db_session)
    result = service.evaluate_ticker("BTLG11.SA")
    assert result is not None
    assert result.valuation_status == VALUATION_STATUS_INDETERMINATE
    assert "fii" in result.reason


def test_evaluate_ticker_picks_up_current_price_and_history(db_session):
    asset = _make_asset(db_session, currency="USD")
    fundamentals = FundamentalsRepository(db_session)
    fundamentals.create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2022, 12, 31),
            source="yahoo",
            pe_ratio=Decimal("9"),
            pb_ratio=Decimal("0.9"),
        )
    )
    fundamentals.create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2023, 12, 31),
            source="yahoo",
            pe_ratio=Decimal("11"),
            pb_ratio=Decimal("1.1"),
        )
    )
    fundamentals.create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2024, 12, 31),
            source="yahoo",
            pe_ratio=Decimal("10"),
            pb_ratio=Decimal("1.0"),
            eps=Decimal("2.0"),
            total_equity=Decimal("20000000"),
            shares_outstanding=Decimal("1000000"),
        )
    )
    prices = PriceRepository(db_session)
    prices.create(Price(asset_id=asset.id, date=date(2026, 7, 1), close=Decimal("15")))

    service = ValuationServiceV2(db_session)
    result = service.evaluate_ticker("WEGE3.SA")

    assert result is not None
    assert result.current_price == Decimal("15")
    # sem FCF disponível, só o método de múltiplos contribui — mas isso já é
    # suficiente para uma faixa de valor justo não-indeterminada.
    assert result.fair_value_range.base is not None
    assert "multiplos" in result.methodology
    assert "dcf" not in result.methodology
