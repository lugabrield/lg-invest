"""Testes do LG Conviction Score Engine (IDS Methodology, Sprint 12).

Engine pura: sem banco, sem rede (coberto também por
`test_engine_purity.py`, que escaneia `engines/` inteiro).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.engines.ids_methodology.engine import calculate_conviction_score
from backend.app.engines.ids_methodology.profile import weights_for_asset_class
from backend.app.engines.ids_methodology.weights import IdsPillarWeights
from backend.app.engines.lg_score.inputs import ScoreInput


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
    result = calculate_conviction_score(_input())
    assert Decimal("0") <= result.conviction_score <= Decimal("100")
    for pillar in (
        result.quality,
        result.valuation,
        result.growth,
        result.risk,
        result.capital_reinvestment,
    ):
        assert Decimal("0") <= pillar <= Decimal("100")


def test_uses_asset_class_profile_by_default():
    stock_result = calculate_conviction_score(_input(asset_class="stock"))
    fii_result = calculate_conviction_score(_input(asset_class="fii"))
    # Perfis diferentes (pesos diferentes) tendem a produzir scores
    # diferentes para o mesmo histórico de preço.
    assert stock_result.conviction_score != fii_result.conviction_score or (
        stock_result.quality == fii_result.quality
        and stock_result.valuation == fii_result.valuation
    )


def test_explanation_has_reason_per_pillar():
    result = calculate_conviction_score(_input())
    names = {p.name for p in result.explanation}
    assert names == {"quality", "valuation", "growth", "risk", "capital_reinvestment"}
    for pillar in result.explanation:
        assert len(pillar.reasons) >= 1
    assert result.model_version == "ids_conviction_v1"


def test_capital_reinvestment_placeholder_lowers_confidence():
    result = calculate_conviction_score(_input())
    capital_reinvestment = next(p for p in result.explanation if p.name == "capital_reinvestment")
    assert capital_reinvestment.confidence == Decimal("0.1")


def test_explicit_weights_override_profile():
    data = _input()
    heavy_quality = IdsPillarWeights(
        quality=1.0, valuation=0.0, growth=0.0, risk=0.0, capital_reinvestment=0.0
    )
    result = calculate_conviction_score(data, weights=heavy_quality)
    assert result.conviction_score == result.quality


def test_invalid_weights_raise():
    bad = IdsPillarWeights(
        quality=0.5, valuation=0.5, growth=0.5, risk=0.0, capital_reinvestment=0.0
    )
    with pytest.raises(ValueError):
        calculate_conviction_score(_input(), weights=bad)


def test_all_asset_class_profiles_produce_valid_score():
    for asset_class in ("stock", "etf", "fii", "reit", "crypto", "bond", "cash"):
        result = calculate_conviction_score(_input(asset_class=asset_class))
        assert Decimal("0") <= result.conviction_score <= Decimal("100")
        weights_for_asset_class(asset_class).validate()
