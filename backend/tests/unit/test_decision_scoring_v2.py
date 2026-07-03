"""Testes do score de compra v2 do Decision Engine (Sprint 18)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.decision.inputs import DecisionInput
from backend.app.engines.decision.scoring import compute_buy_score_v2


def _input(
    lg=80, weight="0.10", conviction=None, class_drift=None, asset_class="stock"
) -> DecisionInput:
    return DecisionInput(
        ticker="WEGE3.SA",
        asset_class=asset_class,
        lg_score=Decimal(str(lg)),
        confidence=Decimal("0.8"),
        current_weight=Decimal(weight),
        conviction_score=Decimal(str(conviction)) if conviction is not None else None,
        class_drift_pct=Decimal(str(class_drift)) if class_drift is not None else None,
    )


def test_score_within_zero_one():
    s = compute_buy_score_v2(_input())
    assert Decimal("0") <= s.score <= Decimal("1")


def test_uses_conviction_score_when_available():
    s = compute_buy_score_v2(_input(lg=50, conviction=90))
    assert s.lg_norm == Decimal("0.9")
    assert "Conviction" in s.reasons[0]


def test_falls_back_to_lg_score_when_conviction_missing():
    s = compute_buy_score_v2(_input(lg=80, conviction=None))
    assert s.lg_norm == Decimal("0.8")
    assert "indisponível" in s.reasons[0]


def test_underweight_class_adds_bonus():
    s = compute_buy_score_v2(_input(class_drift="-0.20"))
    assert s.gap == Decimal("0.20")
    assert "subalocada" in s.reasons[1]


def test_overweight_class_gives_no_bonus():
    s = compute_buy_score_v2(_input(class_drift="0.10"))
    assert s.gap == Decimal("0")


def test_no_target_configured_gives_no_bonus():
    s = compute_buy_score_v2(_input(class_drift=None))
    assert s.gap == Decimal("0")
    assert "sem meta" in s.reasons[1]


def test_higher_conviction_increases_score():
    low = compute_buy_score_v2(_input(conviction=30))
    high = compute_buy_score_v2(_input(conviction=90))
    assert high.score > low.score


def test_lower_weight_increases_score():
    concentrated = compute_buy_score_v2(_input(weight="0.40"))
    small = compute_buy_score_v2(_input(weight="0.05"))
    assert small.score > concentrated.score
