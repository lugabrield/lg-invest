"""Testes dos pilares do LG Score, com foco em dados ausentes e proxies."""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.lg_score.inputs import ScoreInput
from backend.app.engines.lg_score.normalization import NEUTRAL
from backend.app.engines.lg_score.pillars import (
    allocation_pillar,
    growth_pillar,
    quality_pillar,
    risk_pillar,
    valuation_pillar,
)


def _h(prices: list[float]) -> list[Decimal]:
    return [Decimal(str(p)) for p in prices]


def test_valuation_neutral_without_history():
    data = ScoreInput(ticker="X", asset_class="stock", price_history=[])
    pillar = valuation_pillar(data)
    assert pillar.score == NEUTRAL
    assert pillar.confidence <= Decimal("0.2")
    assert any("ausente" in r.lower() or "neutral" in r.lower() for r in pillar.reasons)


def test_growth_neutral_without_history():
    data = ScoreInput(ticker="X", asset_class="stock", price_history=_h([10]))
    pillar = growth_pillar(data)
    assert pillar.score == NEUTRAL


def test_risk_neutral_without_history():
    data = ScoreInput(ticker="X", asset_class="stock", price_history=_h([10]))
    pillar = risk_pillar(data)
    assert pillar.score == NEUTRAL


def test_valuation_cheaper_scores_higher():
    # Preço atual abaixo da média -> nota acima de 50.
    data = ScoreInput(ticker="X", asset_class="stock", price_history=_h([50, 50, 50, 40]))
    pillar = valuation_pillar(data)
    assert pillar.score > NEUTRAL


def test_valuation_expensive_scores_lower():
    # Preço atual acima da média -> nota abaixo de 50.
    data = ScoreInput(ticker="X", asset_class="stock", price_history=_h([40, 40, 40, 60]))
    pillar = valuation_pillar(data)
    assert pillar.score < NEUTRAL


def test_growth_positive_scores_higher():
    data = ScoreInput(ticker="X", asset_class="stock", price_history=_h([10, 12, 15, 20]))
    pillar = growth_pillar(data)
    assert pillar.score > NEUTRAL


def test_quality_uses_class_base():
    etf = quality_pillar(ScoreInput(ticker="VOO", asset_class="etf", price_history=[]))
    crypto = quality_pillar(ScoreInput(ticker="BTC", asset_class="crypto", price_history=[]))
    assert etf.score > crypto.score  # ETF base > cripto base


def test_allocation_neutral_without_target():
    data = ScoreInput(ticker="X", asset_class="stock", current_weight=Decimal("0.2"))
    pillar = allocation_pillar(data)
    assert pillar.score == NEUTRAL


def test_allocation_underweight_scores_higher():
    data = ScoreInput(
        ticker="X",
        asset_class="stock",
        current_weight=Decimal("0.10"),
        target_weight=Decimal("0.25"),
    )
    pillar = allocation_pillar(data)
    assert pillar.score > NEUTRAL  # subalocado -> prioridade


def test_allocation_overweight_scores_lower():
    data = ScoreInput(
        ticker="X",
        asset_class="stock",
        current_weight=Decimal("0.40"),
        target_weight=Decimal("0.25"),
    )
    pillar = allocation_pillar(data)
    assert pillar.score < NEUTRAL  # sobrealocado -> menos prioridade
