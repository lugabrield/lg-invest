"""Testes do FundamentalsAnalysisService (Sprint 14) — usa SQLite em
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
from backend.app.services.fundamentals_analysis_service import FundamentalsAnalysisService


def _make_asset(db_session, ticker="WEGE3.SA") -> Asset:
    return AssetRepository(db_session).create(
        Asset(ticker=ticker, name="WEG", asset_class="stock", country="BR", currency="BRL")
    )


def test_analyze_ticker_unknown_asset_returns_none(db_session):
    service = FundamentalsAnalysisService(db_session)
    assert service.analyze_ticker("NOPE9.SA") is None


def test_analyze_ticker_no_snapshots_returns_low_confidence(db_session):
    _make_asset(db_session)
    service = FundamentalsAnalysisService(db_session)
    result = service.analyze_ticker("WEGE3.SA")
    assert result is not None
    assert result.periods_used == 0
    assert result.confidence == "baixa"


def test_analyze_ticker_uses_stored_snapshots(db_session):
    asset = _make_asset(db_session)
    repo = FundamentalsRepository(db_session)
    repo.create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2023, 12, 31),
            source="yahoo",
            revenue=Decimal("800"),
            net_margin=Decimal("0.10"),
        )
    )
    repo.create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2025, 12, 31),
            source="yahoo",
            revenue=Decimal("968"),
            net_margin=Decimal("0.15"),
        )
    )

    service = FundamentalsAnalysisService(db_session)
    result = service.analyze_ticker("WEGE3.SA")

    assert result is not None
    assert result.periods_used == 2
    assert result.revenue_cagr is not None
    assert result.margin_trend == "melhorando"
