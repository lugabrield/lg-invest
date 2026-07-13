"""Testes do DataCoverageService (Sprint 28, Fase 3/7) — ponte banco<->engine.

Cobre a parte de integração que `test_data_coverage_engine.py` não cobre:
ler `FundamentalSnapshot`/`Price` reais do banco, rodar o Fundamentals
Engine para obter CAGR, e devolver `None` para ticker inexistente."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.infrastructure.database.models import Asset, FundamentalSnapshot, Price
from backend.app.services.data_coverage_service import DataCoverageService


def _seed_asset(db, ticker: str = "WEGE3.SA", asset_class: str = "stock") -> Asset:
    asset = Asset(ticker=ticker, name="WEG", asset_class=asset_class, country="BR", currency="BRL")
    db.add(asset)
    db.commit()
    return asset


def test_evaluate_ticker_returns_none_for_unknown_ticker(db_session):
    result = DataCoverageService(db_session).evaluate_ticker("NAOEXISTE.SA")
    assert result is None


def test_evaluate_ticker_with_no_fundamentals_reports_all_missing(db_session):
    _seed_asset(db_session, ticker="WEGE3.SA")

    result = DataCoverageService(db_session).evaluate_ticker("WEGE3.SA")

    assert result is not None
    assert result.ticker == "WEGE3.SA"
    assert result.period_end is None
    assert len(result.missing_field_labels) > 0


def test_evaluate_ticker_reads_real_snapshot_from_db(db_session):
    asset = _seed_asset(db_session, ticker="ALUP4.SA")
    db_session.add(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2025, 12, 31),
            source="yahoo",
            pe_ratio=Decimal("8.4"),
            pb_ratio=Decimal("1.2"),
            dividend_yield=Decimal("0.06"),
        )
    )
    db_session.add(Price(asset_id=asset.id, date=date(2026, 7, 1), close=Decimal("22")))
    db_session.commit()

    result = DataCoverageService(db_session).evaluate_ticker("ALUP4.SA")

    assert result is not None
    assert result.period_end == date(2025, 12, 31)
    field_by_name = {f.field: f for f in result.fields}
    assert field_by_name["pe_ratio"].available is True
    assert field_by_name["pe_ratio"].value == Decimal("8.4")
    assert field_by_name["pe_ratio"].source == "yahoo"
    assert field_by_name["free_cash_flow"].available is False
    assert result.valuation.classification == "insuficiente"


def test_evaluate_ticker_fii_uses_income_purpose(db_session):
    asset = _seed_asset(db_session, ticker="MXRF11.SA", asset_class="fii")
    db_session.add(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2025, 12, 31),
            source="yahoo",
            pb_ratio=Decimal("1.05"),
            dividend_yield=Decimal("0.10"),
        )
    )
    db_session.commit()

    result = DataCoverageService(db_session).evaluate_ticker("MXRF11.SA")

    assert result is not None
    assert result.valuation.classification == "não aplicável"
    assert result.income.score is not None


def test_evaluate_ticker_uses_latest_period_when_multiple_snapshots(db_session):
    asset = _seed_asset(db_session, ticker="WEGE3.SA")
    db_session.add(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2024, 12, 31),
            source="yahoo",
            pe_ratio=Decimal("12"),
        )
    )
    db_session.add(
        FundamentalSnapshot(
            asset_id=asset.id,
            period_end=date(2025, 12, 31),
            source="yahoo",
            pe_ratio=Decimal("15"),
        )
    )
    db_session.commit()

    result = DataCoverageService(db_session).evaluate_ticker("WEGE3.SA")

    assert result is not None
    assert result.period_end == date(2025, 12, 31)
    field_by_name = {f.field: f for f in result.fields}
    assert field_by_name["pe_ratio"].value == Decimal("15")
