"""Testes do IncomeRealEstateEngine — orquestração pura (Sprint 26, Fase 4)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from backend.app.engines.income_real_estate.engine import IncomeRealEstateEngine
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.income_real_estate import (
    DY_STABILITY_STABLE,
    DY_STABILITY_UNSTABLE,
    INSUFFICIENT_DATA_MESSAGE,
    STATUS_ATTRACTIVE,
    STATUS_NEUTRAL,
    STATUS_UNATTRACTIVE,
)

_ENGINE = IncomeRealEstateEngine()


def _snap(ticker: str = "BTLG11.SA", **kwargs) -> FundamentalSnapshotResult:
    base = {
        "ticker": ticker,
        "period_end": date(2024, 12, 31),
        "source": "yahoo",
        "collected_at": datetime(2025, 1, 1),
    }
    base.update(kwargs)
    return FundamentalSnapshotResult(**base)


def test_out_of_scope_asset_class_returns_reason():
    result = _ENGINE.evaluate(
        ticker="WEGE3.SA", asset_class="stock", latest_snapshot=_snap(), history=[]
    )
    assert result.reason is not None
    assert "fora do escopo" in result.reason


def test_no_snapshot_returns_insufficient_data_message():
    result = _ENGINE.evaluate(
        ticker="BTLG11.SA", asset_class="fii", latest_snapshot=None, history=[]
    )
    assert result.reason == INSUFFICIENT_DATA_MESSAGE


def test_no_pvp_and_no_dy_returns_insufficient_data_message():
    snapshot = _snap()
    result = _ENGINE.evaluate(
        ticker="BTLG11.SA", asset_class="fii", latest_snapshot=snapshot, history=[snapshot]
    )
    assert result.reason == INSUFFICIENT_DATA_MESSAGE
    assert result.confidence == "baixa"


def test_cheap_pvp_and_attractive_dy_and_stable_history_is_attractive():
    history = [
        _snap(
            period_end=date(2022, 12, 31), pb_ratio=Decimal("0.85"), dividend_yield=Decimal("0.09")
        ),
        _snap(
            period_end=date(2023, 12, 31), pb_ratio=Decimal("0.85"), dividend_yield=Decimal("0.09")
        ),
        _snap(
            period_end=date(2024, 12, 31), pb_ratio=Decimal("0.85"), dividend_yield=Decimal("0.09")
        ),
    ]
    latest = history[-1]
    result = _ENGINE.evaluate(
        ticker="BTLG11.SA", asset_class="fii", latest_snapshot=latest, history=history
    )
    assert result.status == STATUS_ATTRACTIVE
    assert result.dy_stability == DY_STABILITY_STABLE
    assert result.confidence == "alta"
    assert set(result.methodology) >= {"pvp", "dividend_yield", "dy_stability"}


def test_expensive_pvp_and_low_dy_is_unattractive():
    history = [
        _snap(
            period_end=date(2023, 12, 31), pb_ratio=Decimal("1.3"), dividend_yield=Decimal("0.03")
        ),
        _snap(
            period_end=date(2024, 12, 31), pb_ratio=Decimal("1.3"), dividend_yield=Decimal("0.03")
        ),
    ]
    latest = history[-1]
    result = _ENGINE.evaluate(
        ticker="BTLG11.SA", asset_class="fii", latest_snapshot=latest, history=history
    )
    assert result.status == STATUS_UNATTRACTIVE


def test_neutral_when_signals_are_mixed():
    history = [
        _snap(
            period_end=date(2023, 12, 31), pb_ratio=Decimal("1.0"), dividend_yield=Decimal("0.065")
        ),
        _snap(
            period_end=date(2024, 12, 31), pb_ratio=Decimal("1.0"), dividend_yield=Decimal("0.065")
        ),
    ]
    latest = history[-1]
    result = _ENGINE.evaluate(
        ticker="BTLG11.SA", asset_class="fii", latest_snapshot=latest, history=history
    )
    assert result.status == STATUS_NEUTRAL


def test_unstable_dy_history_reduces_score_and_adds_warning():
    history = [
        _snap(
            period_end=date(2022, 12, 31), pb_ratio=Decimal("0.85"), dividend_yield=Decimal("0.02")
        ),
        _snap(
            period_end=date(2023, 12, 31), pb_ratio=Decimal("0.85"), dividend_yield=Decimal("0.18")
        ),
        _snap(
            period_end=date(2024, 12, 31), pb_ratio=Decimal("0.85"), dividend_yield=Decimal("0.09")
        ),
    ]
    latest = history[-1]
    result = _ENGINE.evaluate(
        ticker="BTLG11.SA", asset_class="fii", latest_snapshot=latest, history=history
    )
    assert result.dy_stability == DY_STABILITY_UNSTABLE
    assert any("instável" in w for w in result.warnings)


def test_reit_always_gets_ffo_limitation_warning_and_capped_confidence():
    history = [
        _snap(
            ticker="O",
            period_end=date(2023, 12, 31),
            pb_ratio=Decimal("0.85"),
            dividend_yield=Decimal("0.09"),
        ),
        _snap(
            ticker="O",
            period_end=date(2024, 12, 31),
            pb_ratio=Decimal("0.85"),
            dividend_yield=Decimal("0.09"),
        ),
    ]
    latest = history[-1]
    result = _ENGINE.evaluate(
        ticker="O", asset_class="reit", latest_snapshot=latest, history=history
    )
    assert any("FFO/AFFO" in w for w in result.warnings)
    assert result.confidence != "alta"


def test_never_uses_dcf_or_pe_methodology():
    history = [
        _snap(
            period_end=date(2023, 12, 31), pb_ratio=Decimal("0.85"), dividend_yield=Decimal("0.09")
        ),
        _snap(
            period_end=date(2024, 12, 31), pb_ratio=Decimal("0.85"), dividend_yield=Decimal("0.09")
        ),
    ]
    latest = history[-1]
    result = _ENGINE.evaluate(
        ticker="BTLG11.SA", asset_class="fii", latest_snapshot=latest, history=history
    )
    assert "dcf" not in result.methodology
    assert "pe_ratio" not in result.methodology
