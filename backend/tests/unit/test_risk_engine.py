"""Testes do Risk Engine v1 (Sprint 16) — puro, sem banco/rede."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from backend.app.engines.risk.engine import RiskEngine
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


def test_crypto_risk_is_policy_high():
    """Sprint 21: cripto é classificada 'alto' por política da metodologia
    (não por indicador ausente) — ver docs/QUALITY_GROWTH_RISK_ENGINES.md."""
    engine = RiskEngine()
    result = engine.evaluate("BTC-USD", "crypto", None)
    assert result.classification == "alto"
    assert result.confidence == "alta"
    assert "política" in result.reason


def test_not_applicable_class_is_indeterminate():
    engine = RiskEngine()
    result = engine.evaluate("LFT-2029", "bond", None)
    assert result.classification == "indeterminado"
    assert "bond" in result.reason


def test_class_without_bands_is_indeterminate():
    engine = RiskEngine()
    result = engine.evaluate("X", "unknown_class", _snapshot())
    assert result.classification == "indeterminado"


def test_no_snapshot_is_indeterminate():
    engine = RiskEngine()
    result = engine.evaluate("WEGE3.SA", "stock", None)
    assert result.classification == "indeterminado"
    assert "snapshot" in result.reason


def test_stock_low_risk():
    engine = RiskEngine()
    snapshot = _snapshot(debt_to_ebitda=Decimal("1"), beta=Decimal("0.6"))
    result = engine.evaluate("WEGE3.SA", "stock", snapshot)
    assert result.classification == "baixo"
    assert result.confidence == "alta"


def test_stock_high_risk():
    engine = RiskEngine()
    snapshot = _snapshot(debt_to_ebitda=Decimal("6"), beta=Decimal("1.8"))
    result = engine.evaluate("WEGE3.SA", "stock", snapshot)
    assert result.classification == "alto"


def test_fii_uses_only_debt_to_ebitda():
    engine = RiskEngine()
    snapshot = _snapshot(debt_to_ebitda=Decimal("1"))
    result = engine.evaluate("HGLG11.SA", "fii", snapshot)
    assert len(result.metrics) == 1
    assert result.classification == "baixo"


def test_missing_metric_lowers_confidence():
    engine = RiskEngine()
    snapshot = _snapshot(debt_to_ebitda=Decimal("1"))
    result = engine.evaluate("WEGE3.SA", "stock", snapshot)
    assert result.confidence == "média"
    beta_verdict = next(m for m in result.metrics if m.field == "beta")
    assert beta_verdict.verdict == "indeterminado"
