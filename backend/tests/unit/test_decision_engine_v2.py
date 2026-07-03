"""Testes do Decision Engine v2 ponta a ponta (Sprint 18).

Engine pura: sem banco, sem rede.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.engines.decision.engine import recommend_v2
from backend.app.engines.decision.inputs import DecisionInput


def _candidate(ticker, lg, weight, conviction=None, class_drift=None, conf="0.8") -> DecisionInput:
    return DecisionInput(
        ticker=ticker,
        asset_class="stock",
        lg_score=Decimal(str(lg)),
        confidence=Decimal(conf),
        current_weight=Decimal(str(weight)),
        conviction_score=Decimal(str(conviction)) if conviction is not None else None,
        class_drift_pct=Decimal(str(class_drift)) if class_drift is not None else None,
    )


def _portfolio() -> list[DecisionInput]:
    return [
        _candidate("WEGE3.SA", 88, "0.20", conviction=85),
        _candidate("ITUB4.SA", 79, "0.25", conviction=None),
        _candidate("VOO", 84, "0.15", conviction=70, class_drift="-0.10"),
    ]


def test_recommend_1000_distributes_and_explains():
    result = recommend_v2(_portfolio(), Decimal("1000"))
    assert result.allocated_amount <= Decimal("1000")
    assert len(result.items) >= 1
    assert result.explanation
    for item in result.items:
        assert item.reasons


def test_allocation_sum_does_not_exceed_amount():
    result = recommend_v2(_portfolio(), Decimal("1000"))
    total = sum((i.amount for i in result.items), start=Decimal("0"))
    assert total <= Decimal("1000")
    assert total == result.allocated_amount


def test_blocked_asset_not_recommended():
    result = recommend_v2(_portfolio(), Decimal("1000"), blocked={"VOO"})
    tickers = {i.ticker for i in result.items}
    assert "VOO" not in tickers


def test_zero_amount_raises():
    with pytest.raises(ValueError):
        recommend_v2(_portfolio(), Decimal("0"))


def test_audit_log_uses_v2_model_version():
    result = recommend_v2(_portfolio(), Decimal("1000"))
    assert result.audit.model_version == "decision_v2"
    assert result.audit.weights["conviction_score_or_lg_score"] == 0.40


def test_items_carry_conviction_score_when_available():
    result = recommend_v2(_portfolio(), Decimal("1000"))
    wege_item = next((i for i in result.items if i.ticker == "WEGE3.SA"), None)
    if wege_item is not None:
        assert wege_item.conviction_score == Decimal("85")


def test_underweight_class_increases_score_vs_no_target():
    with_target = _candidate("A", 80, "0.10", class_drift="-0.30")
    without_target = _candidate("B", 80, "0.10", class_drift=None)
    result = recommend_v2([with_target, without_target], Decimal("1000"))
    amounts = {i.ticker: i.amount for i in result.items}
    assert amounts.get("A", Decimal("0")) >= amounts.get("B", Decimal("0"))
