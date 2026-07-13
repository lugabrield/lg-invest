"""Testes do Post-Allocation Constraints Engine (Sprint 29).

Bug corrigido: um aporte de R$ 1.000.000 numa carteira de R$ 40.000 levava
a exposição em USD a 97,23% quando o máximo configurado era 60% — o
Decision Engine v3 só checava o peso ANTES do aporte, nunca simulava o
peso RESULTANTE depois de somar o aporte. Estes testes cobrem a engine
pura (`apply_post_allocation_constraints`) com números exatos, calculados
à mão a partir da fórmula pedida pelo usuário:

    portfolio_value_after = portfolio_value_before + contribution_amount
    dimension_value_before = dimension.current_weight * portfolio_value_before
    max_dimension_value_after = dimension.max_weight * portfolio_value_after
    room = max(0, max_dimension_value_after - dimension_value_before)

Cenários numerados conforme a especificação do usuário (13 cenários
obrigatórios); os cenários de integração ponta-a-ponta via DecisionService
estão em `test_decision_service_v3_post_allocation.py`.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.decision.allocation import Allocation
from backend.app.engines.decision.inputs import (
    AllocationRuleSignal,
    DecisionInput,
    PolicyLimits,
    PortfolioAggregates,
)
from backend.app.engines.decision.post_allocation import (
    SOURCE_DETAILED_RULE,
    SOURCE_POLICY,
    apply_post_allocation_constraints,
)


def _candidate(
    ticker: str,
    asset_class: str,
    currency: str,
    country: str,
    current_weight: Decimal = Decimal("0"),
    is_international: bool = False,
    rule_signals: tuple[AllocationRuleSignal, ...] = (),
) -> DecisionInput:
    return DecisionInput(
        ticker=ticker,
        asset_class=asset_class,
        lg_score=Decimal("80"),
        confidence=Decimal("1"),
        current_weight=current_weight,
        currency=currency,
        country=country,
        is_international=is_international,
        rule_signals=rule_signals,
    )


def test_scenario_03_extreme_contribution_caps_usd_currency_dimension():
    """Cenário 3: aporte de R$ 1.000.000 numa carteira de R$ 40.000 NÃO pode
    empurrar a exposição em USD acima do máximo configurado (60%) — este é
    exatamente o bug relatado (USD chegava a 97,23%). Números do exemplo
    fornecido pelo usuário: USD atual=28,7%, max=60%, aporte=1.000.000,
    patrimônio=40.000 -> USD permitido depois=624.000; USD atual em R$
    ~11.480 -> máximo adicional ~= 612.520."""
    signal = AllocationRuleSignal(
        dimension_type="currency",
        gap_status="underweight",
        contribution_priority=1,
        rebalance_required=False,
        extreme_overweight=False,
        dimension_key="USD",
        current_weight=Decimal("0.287"),
        max_weight=Decimal("0.60"),
    )
    voo = _candidate("VOO", "etf", "USD", "US", is_international=True, rule_signals=(signal,))
    qqq = _candidate("QQQ", "etf", "USD", "US", is_international=True, rule_signals=(signal,))

    allocations = [
        Allocation(ticker="VOO", amount=Decimal("500000"), buy_score=Decimal("0.9")),
        Allocation(ticker="QQQ", amount=Decimal("500000"), buy_score=Decimal("0.9")),
    ]

    result = apply_post_allocation_constraints(
        allocations,
        {"VOO": voo, "QQQ": qqq},
        portfolio_value_before=Decimal("40000"),
        contribution_amount=Decimal("1000000"),
    )

    total_allocated = sum((a.amount for a in result.allocations), start=Decimal("0"))
    assert total_allocated == Decimal("612520.00")
    assert result.unallocated_amount == Decimal("387480.00")

    usd_capped = next(cd for cd in result.capped_dimensions if cd.dimension_key == "USD")
    assert usd_capped.weight_after == Decimal("0.6")
    assert usd_capped.weight_after <= usd_capped.max_weight
    # Nunca mais 97,23% — o bug relatado nunca deve voltar a acontecer.
    assert usd_capped.weight_after < Decimal("0.9723")


def test_scenario_04_crypto_class_cannot_exceed_max_after_contribution():
    """Cenário 4: a classe cripto (política geral, `max_crypto_weight`)
    não pode ultrapassar seu máximo DEPOIS do aporte, mesmo que o valor
    inicialmente distribuído pela `select_and_distribute` fosse maior."""
    policy = PolicyLimits(max_crypto_weight=Decimal("0.08"))
    aggregates = PortfolioAggregates(crypto_weight=Decimal("0.045"))
    btc = _candidate(
        "BTC-USD", "crypto", "USD", "US", current_weight=Decimal("0.045"), is_international=True
    )

    allocations = [Allocation(ticker="BTC-USD", amount=Decimal("50000"), buy_score=Decimal("0.8"))]

    result = apply_post_allocation_constraints(
        allocations,
        {"BTC-USD": btc},
        portfolio_value_before=Decimal("40000"),
        contribution_amount=Decimal("100000"),
        policy=policy,
        aggregates=aggregates,
    )

    crypto_capped = next(cd for cd in result.capped_dimensions if cd.dimension_key == "crypto")
    assert crypto_capped.source == SOURCE_POLICY
    assert crypto_capped.weight_after == Decimal("0.08")
    assert crypto_capped.weight_after <= Decimal("0.08")
    assert result.allocations[0].amount < Decimal("50000")


def test_scenario_05_fii_class_cannot_exceed_max_after_contribution():
    """Cenário 5: a classe FII (política geral, `target_fii_max`) não pode
    ultrapassar seu máximo DEPOIS do aporte."""
    policy = PolicyLimits(target_fii_max=Decimal("0.05"))
    aggregates = PortfolioAggregates(fii_weight=Decimal("0.02"))
    hglg = _candidate("HGLG11.SA", "fii", "BRL", "BR", current_weight=Decimal("0.02"))

    allocations = [
        Allocation(ticker="HGLG11.SA", amount=Decimal("20000"), buy_score=Decimal("0.7"))
    ]

    result = apply_post_allocation_constraints(
        allocations,
        {"HGLG11.SA": hglg},
        portfolio_value_before=Decimal("40000"),
        contribution_amount=Decimal("100000"),
        policy=policy,
        aggregates=aggregates,
    )

    fii_capped = next(cd for cd in result.capped_dimensions if cd.dimension_key == "fii")
    assert fii_capped.weight_after == Decimal("0.05")
    assert result.allocations[0].amount < Decimal("20000")


def test_scenario_06_individual_asset_cannot_exceed_max_after_contribution():
    """Cenário 6: um ativo individual (ex.: BTC-USD com `max_asset_weight`
    de 8% na política) não pode ultrapassar seu próprio máximo DEPOIS do
    aporte, mesmo isolado de qualquer limite de classe/moeda."""
    policy = PolicyLimits(max_asset_weight=Decimal("0.08"))
    btc = _candidate("BTC-USD", "crypto", "USD", "US", current_weight=Decimal("0.02"))

    allocations = [Allocation(ticker="BTC-USD", amount=Decimal("50000"), buy_score=Decimal("0.8"))]

    result = apply_post_allocation_constraints(
        allocations,
        {"BTC-USD": btc},
        portfolio_value_before=Decimal("40000"),
        contribution_amount=Decimal("100000"),
        policy=policy,
    )

    asset_capped = next(cd for cd in result.capped_dimensions if cd.dimension_type == "asset")
    assert asset_capped.dimension_key == "BTC-USD"
    assert asset_capped.weight_after == Decimal("0.08")
    assert result.allocations[0].amount < Decimal("50000")


def test_scenario_07_insufficient_room_leaves_balance_unallocated():
    """Cenário 7: quando não há espaço suficiente para alocar todo o
    aporte respeitando os limites, o saldo excedente fica NÃO ALOCADO —
    nunca forçado em outro ativo só para chegar em 100% (pedido explícito
    do usuário)."""
    signal = AllocationRuleSignal(
        dimension_type="currency",
        gap_status="underweight",
        contribution_priority=1,
        rebalance_required=False,
        extreme_overweight=False,
        dimension_key="USD",
        current_weight=Decimal("0.287"),
        max_weight=Decimal("0.60"),
    )
    voo = _candidate("VOO", "etf", "USD", "US", is_international=True, rule_signals=(signal,))
    allocations = [Allocation(ticker="VOO", amount=Decimal("1000000"), buy_score=Decimal("0.9"))]

    result = apply_post_allocation_constraints(
        allocations,
        {"VOO": voo},
        portfolio_value_before=Decimal("40000"),
        contribution_amount=Decimal("1000000"),
    )

    assert result.unallocated_amount > Decimal("0")
    total_final = sum((a.amount for a in result.allocations), start=Decimal("0"))
    assert total_final + result.unallocated_amount == Decimal("1000000")


def test_scenario_08_engine_explains_why_balance_was_left_unallocated():
    """Cenário 8: o motor SEMPRE explica por que deixou um saldo não
    alocado — nunca um corte silencioso. `reasons` cita a dimensão, o
    peso resultante, o limite máximo e a origem do limite, e deixa
    explícito que nenhuma venda é sugerida."""
    signal = AllocationRuleSignal(
        dimension_type="currency",
        gap_status="underweight",
        contribution_priority=1,
        rebalance_required=False,
        extreme_overweight=False,
        dimension_key="USD",
        current_weight=Decimal("0.287"),
        max_weight=Decimal("0.60"),
    )
    voo = _candidate("VOO", "etf", "USD", "US", is_international=True, rule_signals=(signal,))
    allocations = [Allocation(ticker="VOO", amount=Decimal("1000000"), buy_score=Decimal("0.9"))]

    result = apply_post_allocation_constraints(
        allocations,
        {"VOO": voo},
        portfolio_value_before=Decimal("40000"),
        contribution_amount=Decimal("1000000"),
    )

    assert len(result.reasons) == 1
    reason = result.reasons[0]
    assert "USD" in reason
    assert "60.0%" in reason
    assert "não foi alocada" in reason
    assert "Nenhuma venda é sugerida" in reason


def test_scenario_13_detailed_rule_takes_precedence_over_policy():
    """Cenário 13: quando existe uma regra detalhada de Target Allocation
    para uma dimensão, ela SEMPRE tem precedência sobre a política geral
    para a MESMA dimensão — mesma regra já estabelecida em
    `eligibility.py::filter_eligible_v3` (Sprint 25, Parte 1), agora
    reaplicada no corte pós-aporte. A política geral tem um teto de
    cripto BEM mais permissivo (20%) que a regra detalhada (8%) — se a
    política fosse usada por engano, o corte aconteceria num peso maior
    (20%) em vez do menor (8%) da regra detalhada."""
    detailed_signal = AllocationRuleSignal(
        dimension_type="class",
        gap_status="neutral",
        contribution_priority=1,
        rebalance_required=False,
        extreme_overweight=False,
        dimension_key="crypto",
        current_weight=Decimal("0.045"),
        max_weight=Decimal("0.08"),
    )
    policy = PolicyLimits(max_crypto_weight=Decimal("0.20"))  # bem mais permissivo
    aggregates = PortfolioAggregates(crypto_weight=Decimal("0.045"))
    btc = _candidate(
        "BTC-USD",
        "crypto",
        "USD",
        "US",
        current_weight=Decimal("0.045"),
        is_international=True,
        rule_signals=(detailed_signal,),
    )

    allocations = [Allocation(ticker="BTC-USD", amount=Decimal("50000"), buy_score=Decimal("0.8"))]

    result = apply_post_allocation_constraints(
        allocations,
        {"BTC-USD": btc},
        portfolio_value_before=Decimal("40000"),
        contribution_amount=Decimal("100000"),
        policy=policy,
        aggregates=aggregates,
    )

    class_capped = [cd for cd in result.capped_dimensions if cd.dimension_type == "class"]
    assert len(class_capped) == 1
    capped = class_capped[0]
    # Precedência confirmada: usou a regra detalhada (8%, `regra_detalhada`)
    # e NÃO a política geral (20%, `politica_geral`) para a mesma dimensão.
    assert capped.source == SOURCE_DETAILED_RULE
    assert capped.max_weight == Decimal("0.08")
    assert capped.weight_after == Decimal("0.08")
