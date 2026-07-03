"""Testes dos pesos da IDS Methodology (Sprint 12).

Cobre o padrão e todos os perfis por classe de ativo: todos devem
somar 1.0, seguindo o mesmo contrato do LG Score (`LGScoreWeights`).
"""

from __future__ import annotations

import pytest

from backend.app.engines.ids_methodology.profile import (
    ASSET_CLASS_PROFILES,
    weights_for_asset_class,
)
from backend.app.engines.ids_methodology.weights import DEFAULT_WEIGHTS, IdsPillarWeights


def test_default_weights_sum_to_one():
    DEFAULT_WEIGHTS.validate()


def test_default_weights_values():
    assert DEFAULT_WEIGHTS.quality == 0.30
    assert DEFAULT_WEIGHTS.valuation == 0.25
    assert DEFAULT_WEIGHTS.growth == 0.20
    assert DEFAULT_WEIGHTS.risk == 0.15
    assert DEFAULT_WEIGHTS.capital_reinvestment == 0.10


def test_invalid_weights_raise():
    bad = IdsPillarWeights(
        quality=0.5, valuation=0.5, growth=0.5, risk=0.0, capital_reinvestment=0.0
    )
    with pytest.raises(ValueError):
        bad.validate()


@pytest.mark.parametrize("asset_class", list(ASSET_CLASS_PROFILES.keys()))
def test_every_asset_class_profile_sums_to_one(asset_class):
    ASSET_CLASS_PROFILES[asset_class].validate()


def test_weights_for_unknown_asset_class_falls_back_to_default():
    weights = weights_for_asset_class("unknown_class")
    assert weights is DEFAULT_WEIGHTS


def test_weights_for_known_asset_class():
    weights = weights_for_asset_class("fii")
    assert weights is ASSET_CLASS_PROFILES["fii"]
    weights.validate()
