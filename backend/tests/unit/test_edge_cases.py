"""Testes de casos extremos e erros esperados (Volume 20, prompt 12).

Cobre entradas grandes, zeradas e inválidas para garantir que as
engines não quebram e respeitam os limites.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.engines.decision.allocation import select_and_distribute
from backend.app.engines.decision.engine import recommend
from backend.app.engines.decision.inputs import DEFAULT_CONFIG, DecisionInput
from backend.app.engines.decision.scoring import BuyScore
from backend.app.engines.lg_score.engine import calculate_lg_score
from backend.app.engines.lg_score.inputs import ScoreInput
from backend.app.engines.portfolio.engine import build_summary
from backend.app.engines.portfolio.inputs import PositionInput


def test_large_portfolio_stays_consistent():
    positions = [
        PositionInput(f"T{i}", "stock", "BRL", Decimal("10"), Decimal("10"), Decimal("11"))
        for i in range(500)
    ]
    summary = build_summary(positions)
    assert summary.total_value == Decimal("55000")  # 500 * 10 * 11
    weight_sum = sum((p.weight for p in summary.positions), start=Decimal("0"))
    assert weight_sum == pytest.approx(Decimal("1"))


def test_large_amount_allocation_respects_cap():
    scores = [
        BuyScore(f"T{i}", Decimal("0.9"), Decimal("0.8"), Decimal("0"), Decimal("0.9"), [])
        for i in range(8)
    ]
    allocs = select_and_distribute(scores, Decimal("1000000"), DEFAULT_CONFIG)
    total = sum((a.amount for a in allocs), start=Decimal("0"))
    assert total <= Decimal("1000000")


def test_lg_score_all_zero_prices():
    data = ScoreInput(ticker="X", asset_class="stock", price_history=[Decimal("0")] * 10)
    result = calculate_lg_score(data)
    assert Decimal("0") <= result.lg_score <= Decimal("100")


def test_decision_negative_amount_raises():
    candidates = [DecisionInput("A", "stock", Decimal("80"), Decimal("0.8"), Decimal("0.1"))]
    with pytest.raises(ValueError):
        recommend(candidates, Decimal("-100"))


def test_portfolio_single_asset_full_concentration():
    positions = [PositionInput("ONLY", "stock", "BRL", Decimal("10"), Decimal("10"), Decimal("10"))]
    summary = build_summary(positions)
    assert summary.concentration_hhi == Decimal("1")
    assert summary.effective_number_of_assets == Decimal("1")


def test_decision_all_overconcentrated_returns_empty():
    candidates = [
        DecisionInput("A", "stock", Decimal("80"), Decimal("0.8"), Decimal("0.9")),
        DecisionInput("B", "etf", Decimal("70"), Decimal("0.7"), Decimal("0.8")),
    ]
    result = recommend(candidates, Decimal("1000"))
    assert result.items == []
    assert len(result.ignored) == 2
