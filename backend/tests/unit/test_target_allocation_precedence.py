"""Testes de `engines/target_allocation/precedence.py` (ajuste UX
Configurações/alocação, pós-Sprint 25).

Cobre a mesma precedência já usada para BLOQUEIO no Decision Engine 3.0
(`eligibility.py::filter_eligible_v3`) — aqui só para exibição — e a
detecção de conflitos entre alocação simples (v1), regras detalhadas
(v2) e política geral. Nenhum destes testes toca banco: tudo é `RuleLike`/
`PolicyLike` puro.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.target_allocation.precedence import (
    CONFLICT_MIN_GREATER_THAN_TARGET,
    CONFLICT_SIMPLE_VS_DETAILED,
    CONFLICT_SUM_NOT_100,
    SOURCE_DETAILED_RULE,
    SOURCE_GENERAL_POLICY,
    PolicyLike,
    RuleLike,
    detect_conflicts,
    resolve_effective_limits,
)


def _policy(
    *,
    max_asset_weight=Decimal("0.15"),
    max_crypto_weight=Decimal("0.05"),
    target_fii_max=Decimal("0.15"),
) -> PolicyLike:
    return PolicyLike(
        max_asset_weight=max_asset_weight,
        max_crypto_weight=max_crypto_weight,
        target_fii_max=target_fii_max,
    )


# --- resolve_effective_limits: precedência regra > política > nenhum -------


def test_class_fii_uses_policy_fallback_when_no_detailed_rule():
    limits = resolve_effective_limits([], _policy())
    fii = next(
        lim for lim in limits if lim.dimension_type == "class" and lim.dimension_key == "fii"
    )
    assert fii.source == SOURCE_GENERAL_POLICY
    assert fii.max_weight == Decimal("0.15")


def test_class_fii_detailed_rule_overrides_policy():
    rules = [
        RuleLike(
            dimension_type="class",
            dimension_key="fii",
            min_weight=None,
            target_weight=None,
            max_weight=Decimal("0.25"),
            priority=0,
        )
    ]
    limits = resolve_effective_limits(rules, _policy(target_fii_max=Decimal("0.15")))
    fii = next(
        lim for lim in limits if lim.dimension_type == "class" and lim.dimension_key == "fii"
    )
    assert fii.source == SOURCE_DETAILED_RULE
    assert fii.max_weight == Decimal("0.25")
    assert fii.overridden_policy_value == Decimal("0.15")


def test_class_crypto_uses_policy_fallback_when_no_detailed_rule():
    limits = resolve_effective_limits([], _policy())
    crypto = next(
        lim for lim in limits if lim.dimension_type == "class" and lim.dimension_key == "crypto"
    )
    assert crypto.source == SOURCE_GENERAL_POLICY
    assert crypto.max_weight == Decimal("0.05")


def test_asset_specific_rule_overrides_policy_only_for_that_ticker():
    rules = [
        RuleLike(
            dimension_type="asset",
            dimension_key="VOO",
            min_weight=None,
            target_weight=None,
            max_weight=Decimal("0.20"),
            priority=0,
        )
    ]
    limits = resolve_effective_limits(rules, _policy(max_asset_weight=Decimal("0.15")))

    voo = next(
        lim for lim in limits if lim.dimension_type == "asset" and lim.dimension_key == "VOO"
    )
    assert voo.source == SOURCE_DETAILED_RULE
    assert voo.max_weight == Decimal("0.20")
    assert voo.overridden_policy_value == Decimal("0.15")

    generic = next(
        lim for lim in limits if lim.dimension_type == "asset" and lim.dimension_key != "VOO"
    )
    assert generic.source == SOURCE_GENERAL_POLICY
    assert generic.max_weight == Decimal("0.15")


def test_currency_and_country_rules_have_no_policy_fallback():
    rules = [
        RuleLike(
            dimension_type="currency",
            dimension_key="USD",
            min_weight=None,
            target_weight=None,
            max_weight=Decimal("0.60"),
            priority=0,
        )
    ]
    limits = resolve_effective_limits(rules, _policy())
    usd = next(lim for lim in limits if lim.dimension_type == "currency")
    assert usd.source == SOURCE_DETAILED_RULE
    assert usd.max_weight == Decimal("0.60")
    assert usd.overridden_policy_value is None


def test_no_rules_and_no_policy_produces_no_limits():
    limits = resolve_effective_limits([], None)
    assert limits == []


def test_rule_without_max_weight_never_appears_as_a_limit():
    rules = [
        RuleLike(
            dimension_type="class",
            dimension_key="stock",
            min_weight=Decimal("0.10"),
            target_weight=Decimal("0.20"),
            max_weight=None,
            priority=0,
        )
    ]
    limits = resolve_effective_limits(rules, None)
    assert all(
        not (lim.dimension_type == "class" and lim.dimension_key == "stock") for lim in limits
    )


# --- detect_conflicts --------------------------------------------------------


def test_detects_conflict_between_simple_and_detailed_target():
    rules = [
        RuleLike(
            dimension_type="class",
            dimension_key="fii",
            min_weight=None,
            target_weight=Decimal("0.25"),
            max_weight=None,
            priority=0,
        )
    ]
    conflicts = detect_conflicts(rules, {"fii": Decimal("0.15")})
    assert any(c.kind == CONFLICT_SIMPLE_VS_DETAILED for c in conflicts)


def test_no_conflict_when_simple_and_detailed_targets_match():
    rules = [
        RuleLike(
            dimension_type="class",
            dimension_key="fii",
            min_weight=None,
            target_weight=Decimal("0.15"),
            max_weight=None,
            priority=0,
        )
    ]
    conflicts = detect_conflicts(rules, {"fii": Decimal("0.15")})
    assert not any(c.kind == CONFLICT_SIMPLE_VS_DETAILED for c in conflicts)


def test_no_conflict_when_detailed_rule_has_no_target_set():
    rules = [
        RuleLike(
            dimension_type="class",
            dimension_key="fii",
            min_weight=None,
            target_weight=None,
            max_weight=Decimal("0.30"),
            priority=0,
        )
    ]
    conflicts = detect_conflicts(rules, {"fii": Decimal("0.15")})
    assert not any(c.kind == CONFLICT_SIMPLE_VS_DETAILED for c in conflicts)


def test_detects_sum_not_100_across_class_rules():
    rules = [
        RuleLike("class", "fii", None, Decimal("0.20"), None, 0),
        RuleLike("class", "stock", None, Decimal("0.30"), None, 0),
    ]
    conflicts = detect_conflicts(rules, {})
    assert any(c.kind == CONFLICT_SUM_NOT_100 for c in conflicts)


def test_no_sum_conflict_when_class_targets_sum_to_100():
    rules = [
        RuleLike("class", "fii", None, Decimal("0.50"), None, 0),
        RuleLike("class", "stock", None, Decimal("0.50"), None, 0),
    ]
    conflicts = detect_conflicts(rules, {})
    assert not any(c.kind == CONFLICT_SUM_NOT_100 for c in conflicts)


def test_no_sum_conflict_when_no_class_rules_have_target_set():
    rules = [
        RuleLike("class", "fii", None, None, Decimal("0.30"), 0),
    ]
    conflicts = detect_conflicts(rules, {})
    assert not any(c.kind == CONFLICT_SUM_NOT_100 for c in conflicts)


def test_detects_min_greater_than_target_on_existing_data():
    # Defensivo: cobre dados que possam ter sido salvos antes da validação
    # de `set_rule` existir, não só o caminho de escrita nova.
    rules = [
        RuleLike("class", "fii", Decimal("0.30"), Decimal("0.20"), None, 0),
    ]
    conflicts = detect_conflicts(rules, {})
    assert any(c.kind == CONFLICT_MIN_GREATER_THAN_TARGET for c in conflicts)


def test_no_min_greater_than_target_conflict_when_consistent():
    rules = [
        RuleLike("class", "fii", Decimal("0.10"), Decimal("0.20"), None, 0),
    ]
    conflicts = detect_conflicts(rules, {})
    assert not any(c.kind == CONFLICT_MIN_GREATER_THAN_TARGET for c in conflicts)


def test_no_conflicts_at_all_for_empty_inputs():
    assert detect_conflicts([], {}) == []
