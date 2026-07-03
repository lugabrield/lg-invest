"""Testes do Quality Engine v1 (Sprint 16) — puro, sem banco/rede."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from backend.app.engines.quality.engine import QualityEngine
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


def test_non_applicable_class_is_indeterminate():
    engine = QualityEngine()
    result = engine.evaluate("HGLG11.SA", "fii", None)
    assert result.classification == "indeterminado"
    assert "fii" in result.reason


def test_no_snapshot_is_indeterminate():
    engine = QualityEngine()
    result = engine.evaluate("WEGE3.SA", "stock", None)
    assert result.classification == "indeterminado"
    assert "snapshot" in result.reason


def test_strong_quality():
    engine = QualityEngine()
    snapshot = _snapshot(
        roe=Decimal("0.20"), net_margin=Decimal("0.20"), debt_to_ebitda=Decimal("1")
    )
    result = engine.evaluate("WEGE3.SA", "stock", snapshot)
    assert result.classification == "alta"
    assert result.confidence == "alta"


def test_weak_quality():
    engine = QualityEngine()
    snapshot = _snapshot(
        roe=Decimal("0.03"), net_margin=Decimal("0.01"), debt_to_ebitda=Decimal("6")
    )
    result = engine.evaluate("WEGE3.SA", "stock", snapshot)
    assert result.classification == "baixa"


def test_missing_metric_lowers_confidence():
    engine = QualityEngine()
    snapshot = _snapshot(roe=Decimal("0.20"), net_margin=Decimal("0.20"))
    result = engine.evaluate("WEGE3.SA", "stock", snapshot)
    assert result.confidence == "média"
    debt_verdict = next(m for m in result.metrics if m.field == "debt_to_ebitda")
    assert debt_verdict.verdict == "indeterminado"
