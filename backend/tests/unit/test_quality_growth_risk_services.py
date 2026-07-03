"""Testes dos serviços de qualidade, crescimento e risco (Sprint 16) —
usa SQLite em memória (fixture `db_session`), sem rede.
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
from backend.app.services.growth_service import GrowthService
from backend.app.services.quality_service import QualityService
from backend.app.services.risk_service import RiskService


def _make_asset(db_session, ticker="WEGE3.SA", asset_class="stock") -> Asset:
    return AssetRepository(db_session).create(
        Asset(ticker=ticker, name="X", asset_class=asset_class, country="BR", currency="BRL")
    )


# --- QualityService ---------------------------------------------------


def test_quality_service_unknown_asset_returns_none(db_session):
    assert QualityService(db_session).evaluate_ticker("NOPE9.SA") is None


def test_quality_service_uses_latest_snapshot(db_session):
    asset = _make_asset(db_session)
    FundamentalsRepository(db_session).create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2026, 6, 30),
            source="yahoo",
            roe=Decimal("0.20"),
            net_margin=Decimal("0.20"),
            debt_to_ebitda=Decimal("1"),
        )
    )
    result = QualityService(db_session).evaluate_ticker("WEGE3.SA")
    assert result is not None
    assert result.classification == "alta"


# --- RiskService --------------------------------------------------------


def test_risk_service_unknown_asset_returns_none(db_session):
    assert RiskService(db_session).evaluate_ticker("NOPE9.SA") is None


def test_risk_service_uses_latest_snapshot(db_session):
    asset = _make_asset(db_session)
    FundamentalsRepository(db_session).create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2026, 6, 30),
            source="yahoo",
            debt_to_ebitda=Decimal("6"),
            beta=Decimal("1.8"),
        )
    )
    result = RiskService(db_session).evaluate_ticker("WEGE3.SA")
    assert result is not None
    assert result.classification == "alto"


# --- GrowthService --------------------------------------------------------


def test_growth_service_unknown_asset_returns_none(db_session):
    assert GrowthService(db_session).evaluate_ticker("NOPE9.SA") is None


def test_growth_service_uses_fundamentals_analysis(db_session):
    asset = _make_asset(db_session)
    repo = FundamentalsRepository(db_session)
    repo.create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2023, 12, 31),
            source="yahoo",
            revenue=Decimal("800"),
            net_income=Decimal("100"),
        )
    )
    repo.create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2025, 12, 31),
            source="yahoo",
            revenue=Decimal("1200"),
            net_income=Decimal("160"),
        )
    )

    result = GrowthService(db_session).evaluate_ticker("WEGE3.SA")

    assert result is not None
    assert result.classification == "forte"
