"""Testes do score de compra do Decision Engine (Volume 17 §10)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.decision.inputs import DecisionInput
from backend.app.engines.decision.scoring import compute_buy_score


def _input(lg=80, weight="0.10", target=None) -> DecisionInput:
    return DecisionInput(
        ticker="WEGE3.SA",
        asset_class="stock",
        lg_score=Decimal(str(lg)),
        confidence=Decimal("0.8"),
        current_weight=Decimal(weight),
        target_weight=Decimal(str(target)) if target is not None else None,
    )


def test_score_within_zero_one():
    s = compute_buy_score(_input())
    assert Decimal("0") <= s.score <= Decimal("1")


def test_higher_lg_score_increases_buy_score():
    low = compute_buy_score(_input(lg=40))
    high = compute_buy_score(_input(lg=95))
    assert high.score > low.score


def test_lower_weight_increases_buy_score():
    concentrated = compute_buy_score(_input(weight="0.40"))
    small = compute_buy_score(_input(weight="0.05"))
    assert small.score > concentrated.score


def test_gap_zero_without_target():
    s = compute_buy_score(_input(target=None))
    assert s.gap == Decimal("0")


def test_underweight_target_adds_gap():
    s = compute_buy_score(_input(weight="0.10", target="0.25"))
    assert s.gap == Decimal("0.15")


def test_formula_components():
    # lg=80 -> norm 0.8; weight 0.10 -> conc_inv 0.90; sem target -> gap 0
    # score = 0.50*0.8 + 0.30*0 + 0.20*0.90 = 0.40 + 0 + 0.18 = 0.58
    s = compute_buy_score(_input(lg=80, weight="0.10"))
    assert s.score == Decimal("0.58")


# --- score_breakdown estruturado (Sprint 25, Parte 4) -----------------------


def test_score_breakdown_has_three_factors_with_labels():
    s = compute_buy_score(_input())
    labels = [f.label for f in s.factors]
    assert labels == ["LG Score", "Gap de alocação", "Concentração invertida"]


def test_score_breakdown_contributions_sum_to_score():
    s = compute_buy_score(_input(lg=80, weight="0.10", target="0.25"))
    total = sum((f.contribution for f in s.factors), start=Decimal("0"))
    assert total == s.score


def test_score_breakdown_weights_match_formula_weights():
    s = compute_buy_score(_input())
    weights = [f.weight for f in s.factors]
    assert weights == [Decimal("0.50"), Decimal("0.30"), Decimal("0.20")]
