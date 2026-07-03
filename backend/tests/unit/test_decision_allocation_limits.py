"""Testes diretos da normalização de pesos do Decision Engine.

Cobre o branch em que a soma dos pesos clampados excede 1.0 e precisa
ser reduzida proporcionalmente, mantendo o teto máximo.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.decision.allocation import _apply_min_max, select_and_distribute
from backend.app.engines.decision.inputs import DecisionConfig
from backend.app.engines.decision.scoring import BuyScore


def _cfg() -> DecisionConfig:
    return DecisionConfig()


def test_apply_min_max_sum_within_one():
    # Dois ativos 0.6/0.4: 0.6 vira 0.5 (teto), 0.4 fica -> soma 0.9 <= 1.0.
    weights = {"A": Decimal("0.6"), "B": Decimal("0.4")}
    result = _apply_min_max(weights, _cfg())
    assert result["A"] == Decimal("0.5")
    assert result["B"] == Decimal("0.4")


def test_apply_min_max_boosts_below_minimum():
    # Peso 0.02 abaixo do mínimo 0.10 é elevado ao mínimo.
    weights = {"A": Decimal("0.98"), "B": Decimal("0.02")}
    result = _apply_min_max(weights, _cfg())
    assert result["B"] == Decimal("0.10")
    assert result["A"] <= Decimal("0.50")  # teto respeitado


def test_apply_min_max_reduces_when_sum_exceeds_one():
    # Vários pesos que, após o mínimo, somam mais que 1.0 -> redução proporcional.
    weights = {
        "A": Decimal("0.30"),
        "B": Decimal("0.30"),
        "C": Decimal("0.30"),
        "D": Decimal("0.30"),
    }
    result = _apply_min_max(weights, _cfg())
    total = sum(result.values(), start=Decimal("0"))
    # Após redução a soma deve caber em ~1.0 e nenhum peso acima do teto.
    assert total <= Decimal("1.0000001")
    for w in result.values():
        assert w <= Decimal("0.50")
        assert w >= Decimal("0.10")


def test_distribute_many_high_scores_sum_within_amount():
    scores = [
        BuyScore(f"T{i}", Decimal("0.9"), Decimal("0.8"), Decimal("0"), Decimal("0.9"), [])
        for i in range(6)
    ]
    allocs = select_and_distribute(scores, Decimal("3000"), _cfg())
    total = sum((a.amount for a in allocs), start=Decimal("0"))
    assert total <= Decimal("3000")
    for a in allocs:
        assert a.amount <= Decimal("1500.00")  # 50% de 3000
