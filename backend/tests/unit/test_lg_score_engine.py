"""Testes do LG Score Engine v1 (Volume 20, prompt 9; Volume 18 §14).

Engine pura: sem banco, sem rede.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.lg_score.engine import calculate_lg_score
from backend.app.engines.lg_score.inputs import ScoreInput
from backend.app.engines.lg_score.weights import LGScoreWeights


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


def test_score_within_bounds():
    result = calculate_lg_score(_input())
    assert Decimal("0") <= result.lg_score <= Decimal("100")
    for pillar in (result.quality, result.valuation, result.growth, result.risk, result.allocation):
        assert Decimal("0") <= pillar <= Decimal("100")


def test_returns_all_partial_scores():
    result = calculate_lg_score(_input())
    assert result.quality is not None
    assert result.valuation is not None
    assert result.growth is not None
    assert result.risk is not None
    assert result.allocation is not None
    assert result.model_version == "lg_score_v1"


def test_explanation_has_reason_per_pillar():
    result = calculate_lg_score(_input())
    names = {p.name for p in result.explanation}
    assert names == {"quality", "valuation", "growth", "risk", "allocation"}
    for pillar in result.explanation:
        assert len(pillar.reasons) >= 1


def test_extreme_history_stays_bounded():
    # Crescimento explosivo não deve estourar o teto de 100.
    result = calculate_lg_score(_input(price_history=_history([1, 10, 100, 1000, 10000])))
    assert result.lg_score <= Decimal("100")
    assert result.growth <= Decimal("100")


def test_weights_change_moves_final_score():
    data = _input()
    default = calculate_lg_score(data)
    # Peso total no quality; se quality != final default, o score muda.
    heavy_quality = LGScoreWeights(quality=1.0, valuation=0.0, growth=0.0, risk=0.0, allocation=0.0)
    only_quality = calculate_lg_score(data, weights=heavy_quality)
    assert only_quality.lg_score == default.quality


def test_classification_bands():
    # Constrói um caso e apenas verifica que a classificação é coerente com a faixa.
    result = calculate_lg_score(_input())
    score = result.lg_score
    label = result.classification
    if score >= 90:
        assert label == "Exceptional"
    elif score >= 80:
        assert label == "Excellent"
    elif score >= 70:
        assert label == "Good"
    elif score >= 60:
        assert label == "Neutral"
    elif score >= 40:
        assert label == "Weak"
    else:
        assert label == "Avoid"


def test_invalid_weights_raise():
    bad = LGScoreWeights(quality=0.5, valuation=0.5, growth=0.5, risk=0.0, allocation=0.0)
    import pytest

    with pytest.raises(ValueError):
        calculate_lg_score(_input(), weights=bad)
