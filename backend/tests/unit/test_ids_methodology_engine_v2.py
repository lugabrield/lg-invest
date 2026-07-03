"""Testes do LG Conviction Score v2 (Sprint 17) — puro, sem banco/rede."""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.ids_methodology.engine import calculate_conviction_score_v2
from backend.app.engines.lg_score.inputs import ScoreInput
from backend.app.schemas.growth import GrowthResult
from backend.app.schemas.quality import QualityResult
from backend.app.schemas.risk import RiskResult
from backend.app.schemas.valuation import ValuationResult


def _input(**kwargs) -> ScoreInput:
    base = {
        "ticker": "WEGE3.SA",
        "asset_class": "stock",
        "price_history": [Decimal(str(p)) for p in [30, 31, 32, 33, 34, 35, 36, 37, 38, 40]],
    }
    base.update(kwargs)
    return ScoreInput(**base)


def test_v2_without_real_results_matches_full_fallback():
    result = calculate_conviction_score_v2(_input())
    assert result.model_version == "ids_conviction_v2"
    assert Decimal("0") <= result.conviction_score <= Decimal("100")
    for pillar in result.explanation:
        assert "proxy de preço v1" in pillar.reasons[0] or pillar.name == "capital_reinvestment"


def test_v2_with_all_real_results_present():
    result = calculate_conviction_score_v2(
        _input(),
        quality_result=QualityResult(
            ticker="WEGE3.SA", asset_class="stock", classification="alta", confidence="alta"
        ),
        growth_result=GrowthResult(ticker="WEGE3.SA", classification="forte", confidence="alta"),
        risk_result=RiskResult(
            ticker="WEGE3.SA", asset_class="stock", classification="baixo", confidence="alta"
        ),
        valuation_result=ValuationResult(
            ticker="WEGE3.SA", asset_class="stock", classification="barato", confidence="alta"
        ),
    )
    assert result.quality == Decimal("80")
    assert result.growth == Decimal("80")
    assert result.risk == Decimal("80")
    assert result.valuation == Decimal("80")
    # Score alto de qualidade/valuation/crescimento/risco deve puxar o
    # conviction score bem acima do neutro (50).
    assert result.conviction_score > Decimal("70")


def test_v2_explanation_has_reason_per_pillar():
    result = calculate_conviction_score_v2(_input())
    names = {p.name for p in result.explanation}
    assert names == {"quality", "valuation", "growth", "risk", "capital_reinvestment"}
    for pillar in result.explanation:
        assert len(pillar.reasons) >= 1
