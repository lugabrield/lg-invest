"""Testes do IncomeRealEstateService (Sprint 26, Fase 4) — usa SQLite em
memória (fixture `db_session`), sem rede.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.infrastructure.database.models.asset import Asset
from backend.app.infrastructure.database.models.fundamental_snapshot import FundamentalSnapshot
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.schemas.income_real_estate import INSUFFICIENT_DATA_MESSAGE, STATUS_ATTRACTIVE
from backend.app.services.income_real_estate_service import IncomeRealEstateService


def _make_asset(db_session, ticker="BTLG11.SA", asset_class="fii", currency="BRL") -> Asset:
    return AssetRepository(db_session).create(
        Asset(ticker=ticker, name="X", asset_class=asset_class, country="BR", currency=currency)
    )


def test_evaluate_ticker_unknown_asset_returns_none(db_session):
    service = IncomeRealEstateService(db_session)
    assert service.evaluate_ticker("NOPE11.SA") is None


def test_evaluate_ticker_no_snapshot_returns_insufficient_data(db_session):
    _make_asset(db_session)
    service = IncomeRealEstateService(db_session)
    result = service.evaluate_ticker("BTLG11.SA")
    assert result is not None
    assert result.reason == INSUFFICIENT_DATA_MESSAGE


def test_evaluate_ticker_uses_persisted_history(db_session):
    asset = _make_asset(db_session)
    fundamentals = FundamentalsRepository(db_session)
    fundamentals.create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2023, 12, 31),
            source="yahoo",
            pb_ratio=Decimal("0.85"),
            dividend_yield=Decimal("0.09"),
        )
    )
    fundamentals.create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2024, 12, 31),
            source="yahoo",
            pb_ratio=Decimal("0.85"),
            dividend_yield=Decimal("0.09"),
        )
    )

    service = IncomeRealEstateService(db_session)
    result = service.evaluate_ticker("BTLG11.SA")

    assert result is not None
    assert result.status == STATUS_ATTRACTIVE
    assert result.dy_own_history_average == Decimal("0.09")


def test_evaluate_ticker_out_of_scope_asset_class(db_session):
    _make_asset(db_session, ticker="WEGE3.SA", asset_class="stock")
    service = IncomeRealEstateService(db_session)
    result = service.evaluate_ticker("WEGE3.SA")
    assert result is not None
    assert "fora do escopo" in result.reason
