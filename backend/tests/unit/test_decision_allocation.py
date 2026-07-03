"""Testes da distribuição do aporte (Volume 7 §7; Volume 17 §14)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.decision.allocation import select_and_distribute
from backend.app.engines.decision.inputs import DEFAULT_CONFIG
from backend.app.engines.decision.scoring import BuyScore


def _score(ticker, score) -> BuyScore:
    return BuyScore(
        ticker=ticker,
        score=Decimal(str(score)),
        lg_norm=Decimal("0.8"),
        gap=Decimal("0"),
        concentration_inverted=Decimal("0.9"),
        reasons=[],
    )


def test_allocation_sum_never_exceeds_amount():
    scores = [_score("A", 0.8), _score("B", 0.6), _score("C", 0.4)]
    allocs = select_and_distribute(scores, Decimal("1000"), DEFAULT_CONFIG)
    total = sum((a.amount for a in allocs), start=Decimal("0"))
    assert total <= Decimal("1000")


def test_max_single_weight_50pct():
    # Um ativo domina; não pode receber mais que 50% do aporte.
    scores = [_score("A", 0.95), _score("B", 0.05)]
    allocs = select_and_distribute(scores, Decimal("1000"), DEFAULT_CONFIG)
    by_ticker = {a.ticker: a.amount for a in allocs}
    assert by_ticker["A"] <= Decimal("500.00")


def test_min_single_weight_limits_number_of_assets():
    # Com mínimo de 10%, no máximo 10 ativos podem ser selecionados.
    scores = [_score(f"T{i}", 0.9 - i * 0.01) for i in range(20)]
    allocs = select_and_distribute(scores, Decimal("5000"), DEFAULT_CONFIG)
    # faixa > 3000 permite até 8 ativos (limite mais restritivo que o 10 do mínimo).
    assert len(allocs) <= 8


def test_assets_count_for_small_amount():
    scores = [_score(f"T{i}", 0.9 - i * 0.05) for i in range(8)]
    allocs = select_and_distribute(scores, Decimal("400"), DEFAULT_CONFIG)
    assert len(allocs) <= 2  # até R$ 500 -> 1 a 2 ativos


def test_empty_when_amount_zero():
    scores = [_score("A", 0.8)]
    assert select_and_distribute(scores, Decimal("0"), DEFAULT_CONFIG) == []


def test_empty_when_no_positive_scores():
    scores = [_score("A", 0), _score("B", 0)]
    assert select_and_distribute(scores, Decimal("1000"), DEFAULT_CONFIG) == []
