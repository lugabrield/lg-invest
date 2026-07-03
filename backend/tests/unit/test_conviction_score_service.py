"""Testes do ConvictionScoreService (Sprint 17) — wiring DB -> engines -> agregador."""

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
from backend.app.services.conviction_score_service import ConvictionScoreService


def _make_asset(db_session, ticker="WEGE3.SA", asset_class="stock") -> Asset:
    return AssetRepository(db_session).create(
        Asset(ticker=ticker, name="X", asset_class=asset_class, country="BR", currency="BRL")
    )


def test_score_ticker_unknown_asset_returns_none(db_session):
    assert ConvictionScoreService(db_session).score_ticker("NOPE9.SA") is None


def test_score_ticker_without_fundamentals_falls_back_to_price_proxy(db_session):
    asset = _make_asset(db_session)
    price_repo = PriceRepository(db_session)
    for day, close in enumerate([Decimal("30") + day for day in range(10)], start=1):
        price_repo.create(Price(asset_id=asset.id, date=date(2026, 1, day), close=close))

    result = ConvictionScoreService(db_session).score_ticker("WEGE3.SA")

    assert result is not None
    assert result.model_version == "ids_conviction_v2"
    assert Decimal("0") <= result.conviction_score <= Decimal("100")


def test_score_ticker_with_fundamentals_uses_real_engines(db_session):
    asset = _make_asset(db_session)
    price_repo = PriceRepository(db_session)
    for day, close in enumerate([Decimal("30") + day for day in range(10)], start=1):
        price_repo.create(Price(asset_id=asset.id, date=date(2026, 1, day), close=close))

    FundamentalsRepository(db_session).create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2026, 6, 30),
            source="yahoo",
            roe=Decimal("0.20"),
            net_margin=Decimal("0.20"),
            debt_to_ebitda=Decimal("1"),
            pe_ratio=Decimal("10"),
            pb_ratio=Decimal("1.2"),
            ev_ebitda=Decimal("6"),
            payout_ratio=Decimal("0.1"),
            beta=Decimal("0.6"),
        )
    )

    result = ConvictionScoreService(db_session).score_ticker("WEGE3.SA")

    assert result is not None
    quality_pillar = next(p for p in result.explanation if p.name == "quality")
    assert "Quality Engine" in quality_pillar.reasons[0]
    valuation_pillar = next(p for p in result.explanation if p.name == "valuation")
    assert "Valuation Engine" in valuation_pillar.reasons[0]
    risk_pillar = next(p for p in result.explanation if p.name == "risk")
    assert "Risk Engine" in risk_pillar.reasons[0]
