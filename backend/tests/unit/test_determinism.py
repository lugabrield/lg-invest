"""Testes de determinismo das engines (Volume 20, prompt 12).

Mesma entrada -> mesma saída, sempre. Fundamental para reprodutibilidade
e auditabilidade (Volume 7 §2).
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.decision.engine import recommend
from backend.app.engines.decision.inputs import DecisionInput
from backend.app.engines.lg_score.engine import calculate_lg_score
from backend.app.engines.lg_score.inputs import ScoreInput
from backend.app.engines.portfolio.engine import build_summary
from backend.app.engines.portfolio.inputs import PositionInput


def _positions():
    return [
        PositionInput("A", "stock", "BRL", Decimal("100"), Decimal("10"), Decimal("12")),
        PositionInput("B", "etf", "BRL", Decimal("50"), Decimal("20"), Decimal("22")),
    ]


def test_portfolio_engine_deterministic():
    r1 = build_summary(_positions())
    r2 = build_summary(_positions())
    assert r1.total_value == r2.total_value
    assert r1.concentration_hhi == r2.concentration_hhi


def test_lg_score_deterministic():
    data = ScoreInput(
        ticker="A",
        asset_class="stock",
        price_history=[Decimal(str(x)) for x in range(10, 40)],
    )
    r1 = calculate_lg_score(data)
    r2 = calculate_lg_score(data)
    assert r1.lg_score == r2.lg_score
    assert r1.confidence == r2.confidence


def test_decision_engine_deterministic():
    candidates = [
        DecisionInput("A", "stock", Decimal("80"), Decimal("0.8"), Decimal("0.1")),
        DecisionInput("B", "etf", Decimal("70"), Decimal("0.7"), Decimal("0.1")),
    ]
    r1 = recommend(candidates, Decimal("1000"))
    r2 = recommend(candidates, Decimal("1000"))
    d1 = {i.ticker: i.amount for i in r1.items}
    d2 = {i.ticker: i.amount for i in r2.items}
    assert d1 == d2
