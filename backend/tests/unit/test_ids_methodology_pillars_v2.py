"""Testes dos pilares v2 da IDS Methodology (Sprint 17) — puro, sem banco/rede."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from backend.app.engines.ids_methodology.pillars import (
    capital_reinvestment_pillar_v2,
    growth_pillar_v2,
    quality_pillar_v2,
    risk_pillar_v2,
    valuation_pillar_v2,
)
from backend.app.engines.lg_score.inputs import ScoreInput
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.growth import GrowthResult
from backend.app.schemas.quality import QualityResult
from backend.app.schemas.risk import RiskResult
from backend.app.schemas.valuation import ValuationResult


def _input(**kwargs) -> ScoreInput:
    base = {
        "ticker": "WEGE3.SA",
        "asset_class": "stock",
        "price_history": [Decimal(str(p)) for p in [30, 31, 32, 33, 34, 35]],
    }
    base.update(kwargs)
    return ScoreInput(**base)


def _snapshot(**kwargs) -> FundamentalSnapshotResult:
    base = {
        "ticker": "WEGE3.SA",
        "period_end": date(2026, 6, 30),
        "source": "yahoo",
        "collected_at": datetime(2026, 7, 2, 12, 0, 0),
    }
    base.update(kwargs)
    return FundamentalSnapshotResult(**base)


def test_quality_pillar_v2_uses_real_result():
    result = QualityResult(
        ticker="WEGE3.SA", asset_class="stock", classification="alta", confidence="alta"
    )
    pillar = quality_pillar_v2(_input(), result)
    assert pillar.score == Decimal("80")
    assert pillar.confidence == Decimal("0.9")
    assert "Quality Engine" in pillar.reasons[0]


def test_quality_pillar_v2_falls_back_when_indeterminate():
    result = QualityResult(
        ticker="WEGE3.SA", asset_class="fii", classification="indeterminado", reason="não aplicável"
    )
    pillar = quality_pillar_v2(_input(), result)
    assert "proxy de preço v1" in pillar.reasons[0]


def test_quality_pillar_v2_falls_back_when_none():
    pillar = quality_pillar_v2(_input(), None)
    assert "proxy de preço v1" in pillar.reasons[0]


def test_growth_pillar_v2_uses_real_result():
    result = GrowthResult(ticker="WEGE3.SA", classification="forte", confidence="alta")
    pillar = growth_pillar_v2(_input(), result)
    assert pillar.score == Decimal("80")


def test_risk_pillar_v2_uses_real_result():
    result = RiskResult(
        ticker="WEGE3.SA", asset_class="stock", classification="baixo", confidence="alta"
    )
    pillar = risk_pillar_v2(_input(), result)
    assert pillar.score == Decimal("80")


def test_valuation_pillar_v2_uses_real_result():
    result = ValuationResult(
        ticker="WEGE3.SA", asset_class="stock", classification="barato", confidence="alta"
    )
    pillar = valuation_pillar_v2(_input(), result)
    assert pillar.score == Decimal("80")


def test_capital_reinvestment_v2_not_applicable_class():
    pillar = capital_reinvestment_pillar_v2("fii", _snapshot(payout_ratio=Decimal("0.95")))
    assert pillar.score == Decimal("50")
    assert "não aplicável" in pillar.reasons[0]


def test_capital_reinvestment_v2_missing_payout():
    pillar = capital_reinvestment_pillar_v2("stock", None)
    assert pillar.score == Decimal("50")
    assert "dado ausente" in pillar.reasons[0]


def test_capital_reinvestment_v2_high_retention():
    pillar = capital_reinvestment_pillar_v2("stock", _snapshot(payout_ratio=Decimal("0.1")))
    assert pillar.score > Decimal("50")


def test_capital_reinvestment_v2_low_retention_scores_lower_than_high_retention():
    low_retention = capital_reinvestment_pillar_v2("stock", _snapshot(payout_ratio=Decimal("0.9")))
    high_retention = capital_reinvestment_pillar_v2("stock", _snapshot(payout_ratio=Decimal("0.1")))
    assert low_retention.score < high_retention.score
