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


# --- Sprint 25, Parte 2.5: teto de alocação para ativo novo da Watchlist ---


def test_apply_min_max_caps_new_asset_below_default_ticket():
    # Sozinho, um ativo normal iria para o teto de 50%; um ativo novo da
    # Watchlist é limitado a 25% (default de `max_new_asset_weight`).
    weights = {"NEW": Decimal("1.0")}
    result = _apply_min_max(weights, _cfg(), new_asset_tickers=frozenset({"NEW"}))
    assert result["NEW"] == Decimal("0.25")


def test_apply_min_max_new_asset_cap_does_not_affect_other_tickers():
    weights = {"NEW": Decimal("0.5"), "OLD": Decimal("0.5")}
    result = _apply_min_max(weights, _cfg(), new_asset_tickers=frozenset({"NEW"}))
    assert result["NEW"] == Decimal("0.25")
    assert result["OLD"] == Decimal("0.5")


def test_select_and_distribute_single_new_asset_never_gets_full_amount():
    """Requisito explícito: um ativo novo nunca recebe 100% do aporte por
    padrão, mesmo sendo o único candidato elegível com o maior score."""
    scores = [BuyScore("NEW", Decimal("1.0"), Decimal("1.0"), Decimal("0"), Decimal("1.0"), [])]
    allocs = select_and_distribute(
        scores, Decimal("1000"), _cfg(), new_asset_tickers=frozenset({"NEW"})
    )
    assert len(allocs) == 1
    assert allocs[0].amount <= Decimal("250.00")


def test_select_and_distribute_new_asset_cap_leaves_remainder_unallocated():
    scores = [BuyScore("NEW", Decimal("1.0"), Decimal("1.0"), Decimal("0"), Decimal("1.0"), [])]
    allocs = select_and_distribute(
        scores, Decimal("1000"), _cfg(), new_asset_tickers=frozenset({"NEW"})
    )
    total = sum((a.amount for a in allocs), start=Decimal("0"))
    assert total < Decimal("1000")


def test_select_and_distribute_without_new_asset_tickers_keeps_old_behavior():
    # frozenset() vazio (default) -> comportamento idêntico ao pré-Sprint 25.
    scores = [BuyScore("ANY", Decimal("1.0"), Decimal("1.0"), Decimal("0"), Decimal("1.0"), [])]
    allocs = select_and_distribute(scores, Decimal("1000"), _cfg())
    assert allocs[0].amount == Decimal("500.00")  # teto padrão de 50%
