"""Testes dos pilares da IDS Methodology (Sprint 12).

Quality/Valuation/Growth/Risk devem produzir exatamente o mesmo
resultado das proxies do LG Score (reaproveitamento deliberado).
Capital Reinvestment deve ser sempre neutro e explícito sobre a
ausência de dado — nunca otimista.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.ids_methodology.pillars import (
    capital_reinvestment_pillar,
    growth_pillar,
    quality_pillar,
    risk_pillar,
    valuation_pillar,
)
from backend.app.engines.lg_score.inputs import ScoreInput
from backend.app.engines.lg_score.normalization import NEUTRAL
from backend.app.engines.lg_score.pillars import growth_pillar as lg_growth_pillar
from backend.app.engines.lg_score.pillars import quality_pillar as lg_quality_pillar
from backend.app.engines.lg_score.pillars import risk_pillar as lg_risk_pillar
from backend.app.engines.lg_score.pillars import valuation_pillar as lg_valuation_pillar


def _history(prices: list[float]) -> list[Decimal]:
    return [Decimal(str(p)) for p in prices]


def _input(**kwargs) -> ScoreInput:
    base = {
        "ticker": "WEGE3.SA",
        "asset_class": "stock",
        "price_history": _history([30, 31, 32, 33, 34, 35, 36, 37, 38, 40]),
    }
    base.update(kwargs)
    return ScoreInput(**base)


def test_quality_pillar_matches_lg_score():
    data = _input()
    assert quality_pillar(data) == lg_quality_pillar(data)


def test_valuation_pillar_matches_lg_score():
    data = _input()
    assert valuation_pillar(data) == lg_valuation_pillar(data)


def test_growth_pillar_matches_lg_score():
    data = _input()
    assert growth_pillar(data) == lg_growth_pillar(data)


def test_risk_pillar_matches_lg_score():
    data = _input()
    assert risk_pillar(data) == lg_risk_pillar(data)


def test_capital_reinvestment_is_always_neutral():
    result = capital_reinvestment_pillar(_input())
    assert result.score == NEUTRAL
    assert result.confidence == Decimal("0.1")
    assert len(result.reasons) == 1
    assert "dado ausente" in result.reasons[0]


def test_capital_reinvestment_neutral_regardless_of_history():
    empty_history = capital_reinvestment_pillar(_input(price_history=[]))
    long_history = capital_reinvestment_pillar(_input(price_history=_history(list(range(1, 100)))))
    assert empty_history.score == long_history.score == NEUTRAL
