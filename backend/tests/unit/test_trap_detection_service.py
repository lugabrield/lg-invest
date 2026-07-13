"""Testes do TrapDetectionService (Sprint 26, Fases 3-4) — usa SQLite em
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
from backend.app.schemas.trap_detection import (
    TRAP_TYPE_FII_YIELD,
    TRAP_TYPE_HIGH_DY,
    TRAP_TYPE_LEVERAGE,
)
from backend.app.services.trap_detection_service import TrapDetectionService


def _make_asset(db_session, ticker="WEGE3.SA", asset_class="stock", currency="BRL") -> Asset:
    return AssetRepository(db_session).create(
        Asset(ticker=ticker, name="X", asset_class=asset_class, country="BR", currency=currency)
    )


def test_evaluate_ticker_unknown_asset_returns_none(db_session):
    service = TrapDetectionService(db_session)
    assert service.evaluate_ticker("NOPE9.SA") is None


def test_evaluate_ticker_no_snapshot_returns_no_flags(db_session):
    _make_asset(db_session)
    service = TrapDetectionService(db_session)
    result = service.evaluate_ticker("WEGE3.SA")
    assert result is not None
    assert result.flags == []
    assert result.reason is not None


def test_evaluate_ticker_out_of_scope_asset_class(db_session):
    _make_asset(db_session, ticker="BOVA11.SA", asset_class="etf")
    service = TrapDetectionService(db_session)
    result = service.evaluate_ticker("BOVA11.SA")
    assert result is not None
    assert "etf" in result.reason


def test_evaluate_ticker_detects_leverage_trap_from_persisted_snapshot(db_session):
    asset = _make_asset(db_session, currency="USD")
    fundamentals = FundamentalsRepository(db_session)
    fundamentals.create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2023, 12, 31),
            source="yahoo",
            pe_ratio=Decimal("15"),
            pb_ratio=Decimal("2.0"),
            roe=Decimal("0.18"),
            debt_to_ebitda=Decimal("7"),
            interest_coverage=Decimal("0.8"),
        )
    )
    fundamentals.create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2024, 12, 31),
            source="yahoo",
            pe_ratio=Decimal("15"),
            pb_ratio=Decimal("2.0"),
            roe=Decimal("0.18"),
            debt_to_ebitda=Decimal("7"),
            interest_coverage=Decimal("0.8"),
        )
    )

    service = TrapDetectionService(db_session)
    result = service.evaluate_ticker("WEGE3.SA")

    assert result is not None
    trap_types = {flag.trap_type for flag in result.flags}
    assert TRAP_TYPE_LEVERAGE in trap_types
    assert result.confidence_penalty > Decimal("0")


def test_evaluate_ticker_fii_routes_to_income_real_estate_detectors(db_session):
    # dy_own_history_average é calculada pelo IncomeRealEstateService a partir
    # de TODO o histórico (inclusive o período mais recente) — com
    # 0.06, 0.06, 0.18 a média é 0.10, então o DY mais recente (0.18) fica
    # 1.8x acima da própria média (>= FII_YIELD_SPIKE_RATIO_HIGH) e também
    # acima de VERY_HIGH_DY_THRESHOLD (0.18), disparando os dois traps.
    asset = _make_asset(db_session, ticker="BTLG11.SA", asset_class="fii", currency="BRL")
    fundamentals = FundamentalsRepository(db_session)
    fundamentals.create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2022, 12, 31),
            source="yahoo",
            dividend_yield=Decimal("0.06"),
        )
    )
    fundamentals.create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2023, 12, 31),
            source="yahoo",
            dividend_yield=Decimal("0.06"),
        )
    )
    fundamentals.create(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2024, 12, 31),
            source="yahoo",
            dividend_yield=Decimal("0.18"),
        )
    )

    service = TrapDetectionService(db_session)
    result = service.evaluate_ticker("BTLG11.SA")

    assert result is not None
    trap_types = {flag.trap_type for flag in result.flags}
    assert TRAP_TYPE_HIGH_DY in trap_types
    assert TRAP_TYPE_FII_YIELD in trap_types
    assert result.confidence_penalty > Decimal("0")
