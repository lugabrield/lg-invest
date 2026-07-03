"""Testes do Growth Engine v1 (Sprint 16) — puro, sem banco/rede."""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.growth.engine import GrowthEngine
from backend.app.schemas.fundamentals_analysis import FundamentalsAnalysisResult


def _analysis(**kwargs) -> FundamentalsAnalysisResult:
    base = {"ticker": "WEGE3.SA", "periods_used": 2}
    base.update(kwargs)
    return FundamentalsAnalysisResult(**base)


def test_no_periods_is_indeterminate():
    engine = GrowthEngine()
    analysis = _analysis(periods_used=0, reason="nenhum snapshot de fundamentos disponível")
    result = engine.evaluate("WEGE3.SA", analysis)
    assert result.classification == "indeterminado"
    assert result.reason is not None


def test_strong_growth():
    engine = GrowthEngine()
    analysis = _analysis(revenue_cagr=Decimal("0.20"), net_income_cagr=Decimal("0.25"))
    result = engine.evaluate("WEGE3.SA", analysis)
    assert result.classification == "forte"
    assert result.confidence == "alta"


def test_weak_growth():
    engine = GrowthEngine()
    analysis = _analysis(revenue_cagr=Decimal("0.01"), net_income_cagr=Decimal("-0.05"))
    result = engine.evaluate("WEGE3.SA", analysis)
    assert result.classification == "fraco"


def test_partial_cagr_lowers_confidence():
    engine = GrowthEngine()
    analysis = _analysis(
        revenue_cagr=Decimal("0.20"),
        net_income_cagr=None,
        net_income_cagr_reason="valor inicial ou final não positivo — CAGR não é significativo",
    )
    result = engine.evaluate("WEGE3.SA", analysis)
    assert result.confidence == "média"
    net_income_verdict = next(m for m in result.metrics if m.field == "net_income_cagr")
    assert net_income_verdict.verdict == "indeterminado"
    assert net_income_verdict.reason is not None
