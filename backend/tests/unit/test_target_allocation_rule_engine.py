"""Testes do Target Allocation Engine v2 (Sprint 24, Fase 3) — puro, sem banco/rede.

Cobre as 4 dimensões (classe/moeda/país/ativo) tratadas de forma
independente, os 4 status (underweight/neutral/overweight/blocked),
prioridade de aporte, `rebalance_required` e a regra de nunca recomendar
venda automática (overweight/blocked nunca tem `contribution_priority` > 0
e a mensagem de overweight nunca sugere vender).
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.target_allocation.engine import (
    AllocationRuleInput,
    TargetAllocationRuleEngine,
)

_ZERO = Decimal("0")


def _rule(
    dimension_type="class",
    dimension_key="fii",
    min_weight=None,
    target_weight=None,
    max_weight=None,
    priority=0,
) -> AllocationRuleInput:
    return AllocationRuleInput(
        dimension_type=dimension_type,
        dimension_key=dimension_key,
        min_weight=min_weight,
        target_weight=target_weight,
        max_weight=max_weight,
        priority=priority,
    )


def test_no_rules_returns_has_rules_false():
    engine = TargetAllocationRuleEngine()
    result = engine.evaluate({}, [])
    assert result.has_rules is False
    assert result.reason is not None
    assert result.evaluations == []


def test_underweight_when_gap_below_negative_tolerance():
    engine = TargetAllocationRuleEngine()
    rules = [_rule(target_weight=Decimal("0.20"))]
    result = engine.evaluate({("class", "fii"): Decimal("0.05")}, rules)
    evaluation = result.evaluations[0]
    assert evaluation.gap_status == "underweight"
    assert evaluation.gap_to_target == Decimal("-0.15")
    assert evaluation.contribution_priority > 0


def test_neutral_within_tolerance():
    engine = TargetAllocationRuleEngine()
    rules = [_rule(target_weight=Decimal("0.20"))]
    result = engine.evaluate(
        {("class", "fii"): Decimal("0.21")}, rules, rebalance_threshold=Decimal("0.03")
    )
    assert result.evaluations[0].gap_status == "neutral"


def test_overweight_when_above_target_but_under_max():
    engine = TargetAllocationRuleEngine()
    rules = [_rule(target_weight=Decimal("0.20"), max_weight=Decimal("0.35"))]
    result = engine.evaluate({("class", "fii"): Decimal("0.30")}, rules)
    evaluation = result.evaluations[0]
    assert evaluation.gap_status == "overweight"
    # Nunca recomenda venda — a mensagem deve orientar pausar aporte, não vender.
    assert "não vender" in evaluation.alert_message
    assert evaluation.contribution_priority == 0


def test_blocked_when_above_max_weight():
    engine = TargetAllocationRuleEngine()
    rules = [_rule(target_weight=Decimal("0.20"), max_weight=Decimal("0.25"))]
    result = engine.evaluate({("class", "fii"): Decimal("0.30")}, rules)
    evaluation = result.evaluations[0]
    assert evaluation.gap_status == "blocked"
    assert evaluation.rebalance_required is True
    assert evaluation.contribution_priority == 0


def test_extreme_overweight_flagged_but_never_recommends_sell():
    engine = TargetAllocationRuleEngine()
    rules = [_rule(dimension_type="class", dimension_key="crypto", max_weight=Decimal("0.05"))]
    # 0.10 > 0.05 * 1.5 (0.075) -> extremo
    result = engine.evaluate({("class", "crypto"): Decimal("0.10")}, rules)
    evaluation = result.evaluations[0]
    assert evaluation.gap_status == "blocked"
    assert evaluation.extreme_overweight is True
    assert "venda automática" in evaluation.alert_message


def test_missing_dimension_key_treated_as_zero_current_weight():
    engine = TargetAllocationRuleEngine()
    rules = [_rule(dimension_type="currency", dimension_key="USD", target_weight=Decimal("0.30"))]
    result = engine.evaluate({}, rules)
    evaluation = result.evaluations[0]
    assert evaluation.current_weight == _ZERO
    assert evaluation.gap_status == "underweight"


def test_priority_field_influences_contribution_priority_ranking():
    engine = TargetAllocationRuleEngine()
    rules = [
        _rule(dimension_key="fii", target_weight=Decimal("0.20"), priority=10),
        _rule(dimension_key="etf", target_weight=Decimal("0.20"), priority=0),
    ]
    current = {("class", "fii"): Decimal("0.10"), ("class", "etf"): Decimal("0.10")}
    result = engine.evaluate(current, rules)
    by_key = {e.dimension_key: e for e in result.evaluations}
    assert by_key["fii"].contribution_priority > by_key["etf"].contribution_priority


def test_dimensions_evaluated_independently_never_mixed():
    engine = TargetAllocationRuleEngine()
    rules = [
        _rule(dimension_type="class", dimension_key="stock", target_weight=Decimal("0.40")),
        _rule(dimension_type="currency", dimension_key="USD", target_weight=Decimal("0.30")),
        _rule(dimension_type="country", dimension_key="US", target_weight=Decimal("0.30")),
        _rule(dimension_type="asset", dimension_key="VOO", target_weight=Decimal("0.10")),
    ]
    current = {
        ("class", "stock"): Decimal("0.40"),
        ("currency", "USD"): Decimal("0.10"),
        ("country", "US"): Decimal("0.05"),
        ("asset", "VOO"): Decimal("0.02"),
    }
    result = engine.evaluate(current, rules)
    assert len(result.evaluations) == 4
    assert result.by_dimension("class")[0].dimension_key == "stock"
    assert result.by_dimension("currency")[0].dimension_key == "USD"
    assert result.by_dimension("country")[0].dimension_key == "US"
    assert result.by_dimension("asset")[0].dimension_key == "VOO"


def test_rebalance_required_true_for_large_underweight_gap():
    engine = TargetAllocationRuleEngine()
    rules = [_rule(target_weight=Decimal("0.30"))]
    result = engine.evaluate(
        {("class", "fii"): Decimal("0.05")}, rules, rebalance_threshold=Decimal("0.05")
    )
    assert result.evaluations[0].rebalance_required is True


def test_no_target_weight_but_within_max_is_neutral():
    engine = TargetAllocationRuleEngine()
    rules = [_rule(max_weight=Decimal("0.30"))]
    result = engine.evaluate({("class", "fii"): Decimal("0.10")}, rules)
    assert result.evaluations[0].gap_status == "neutral"
    assert result.evaluations[0].gap_to_target is None
