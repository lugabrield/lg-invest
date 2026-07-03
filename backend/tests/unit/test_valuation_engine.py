"""Testes do Valuation Engine v1 (Sprint 15) — puro, sem banco/rede."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from backend.app.engines.valuation.engine import ValuationEngine
from backend.app.schemas.fundamentals import FundamentalSnapshotResult


def _snapshot(**kwargs) -> FundamentalSnapshotResult:
    base = {
        "ticker": "WEGE3.SA",
        "period_end": date(2026, 6, 30),
        "source": "yahoo",
        "collected_at": datetime(2026, 7, 2, 12, 0, 0),
    }
    base.update(kwargs)
    return FundamentalSnapshotResult(**base)


def test_not_applicable_class_is_indeterminate():
    engine = ValuationEngine()
    result = engine.evaluate("BTC-USD", "crypto", None)
    assert result.classification == "indeterminado"
    assert result.confidence == "baixa"
    assert "crypto" in result.reason


def test_class_without_bands_is_indeterminate():
    engine = ValuationEngine()
    result = engine.evaluate("X", "unknown_class", _snapshot())
    assert result.classification == "indeterminado"
    assert result.reason is not None


def test_no_snapshot_is_indeterminate():
    engine = ValuationEngine()
    result = engine.evaluate("WEGE3.SA", "stock", None)
    assert result.classification == "indeterminado"
    assert "snapshot" in result.reason


def test_stock_all_cheap_metrics():
    engine = ValuationEngine()
    snapshot = _snapshot(pe_ratio=Decimal("10"), pb_ratio=Decimal("1.2"), ev_ebitda=Decimal("6"))
    result = engine.evaluate("WEGE3.SA", "stock", snapshot)
    assert result.classification == "barato"
    assert result.confidence == "alta"
    assert len(result.metrics) == 3


def test_stock_all_expensive_metrics():
    engine = ValuationEngine()
    snapshot = _snapshot(pe_ratio=Decimal("25"), pb_ratio=Decimal("4"), ev_ebitda=Decimal("16"))
    result = engine.evaluate("WEGE3.SA", "stock", snapshot)
    assert result.classification == "caro"


def test_stock_all_neutral_metrics():
    engine = ValuationEngine()
    snapshot = _snapshot(pe_ratio=Decimal("15"), pb_ratio=Decimal("2"), ev_ebitda=Decimal("10"))
    result = engine.evaluate("WEGE3.SA", "stock", snapshot)
    assert result.classification == "neutro"


def test_stock_missing_one_metric_lowers_confidence():
    engine = ValuationEngine()
    snapshot = _snapshot(pe_ratio=Decimal("10"), pb_ratio=Decimal("1.2"))
    result = engine.evaluate("WEGE3.SA", "stock", snapshot)
    assert result.confidence == "média"
    ev_verdict = next(m for m in result.metrics if m.field == "ev_ebitda")
    assert ev_verdict.verdict == "indeterminado"
    assert ev_verdict.reason is not None


def test_fii_cheap_via_pb_and_dividend_yield():
    engine = ValuationEngine()
    snapshot = _snapshot(pb_ratio=Decimal("0.8"), dividend_yield=Decimal("0.10"))
    result = engine.evaluate("HGLG11.SA", "fii", snapshot)
    assert result.classification == "barato"


def test_fii_expensive_via_pb_and_dividend_yield():
    engine = ValuationEngine()
    snapshot = _snapshot(pb_ratio=Decimal("1.2"), dividend_yield=Decimal("0.05"))
    result = engine.evaluate("HGLG11.SA", "fii", snapshot)
    assert result.classification == "caro"
