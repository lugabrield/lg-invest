"""Testes do ValuationService (Sprint 15) — usa SQLite em memória
(fixture `db_session`), sem rede.
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
from backend.app.services.valuation_service import ValuationService


def _make_asset(db_session, ticker="WEGE3.SA", asset_class="stock") -> Asset:
    return AssetRepository(db_session).create(
        Asset(ticker=ticker, name="X", asset_class=asset_class, country="BR", currency="BRL")
    )


def test_evaluate_ticker_unknown_asset_returns_none(db_session):
    service = ValuationService(db_session)
    assert service.evaluate_ticker("NOPE9.SA") is None


def test_evaluate_ticker_no_snapshot_is_indeterminate(db_session):
    _make_asset(db_session)
    service = ValuationService(db_session)
    result = service.evaluate_ticker("WEGE3.SA")
    assert result is not None
    assert result.classification == "indeterminado"


def test_evaluate_ticker_uses_latest_snapshot(db_session):
    asset = _make_asset(db_session)
    repo = FundamentalsRepository(db_session)
    repo.create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2023, 12, 31),
            source="yahoo",
            pe_ratio=Decimal("25"),
        )
    )
    repo.create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2026, 6, 30),
            source="yahoo",
            pe_ratio=Decimal("10"),
            pb_ratio=Decimal("1.2"),
            ev_ebitda=Decimal("6"),
        )
    )

    service = ValuationService(db_session)
    result = service.evaluate_ticker("WEGE3.SA")

    assert result is not None
    assert result.classification == "barato"


def test_evaluate_ticker_not_applicable_class(db_session):
    _make_asset(db_session, "BTC-USD", asset_class="crypto")
    service = ValuationService(db_session)
    result = service.evaluate_ticker("BTC-USD")
    assert result is not None
    assert result.classification == "indeterminado"
    assert "crypto" in result.reason
