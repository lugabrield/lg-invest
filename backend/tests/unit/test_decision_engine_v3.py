"""Testes do Decision Engine 3.0 (Sprint 24, Fase 4) — engine pura, sem banco.

Cobre: fallback de fundamentos (pilares -> conviction_score -> lg_score),
bônus de alocação-alvo multi-dimensão, bônus de internacionalização,
escala do score pela confiança do dado, bloqueio por Investment Policy
(peso por ativo / cripto agregado / FII agregado) e por Target Allocation
Rule Engine v2 (`gap_status == "blocked"`), e a regra de ouro: nunca
recomendar venda, mesmo em bloqueio ou desvio extremo.

Sprint 25 (Parte 1): a precedência entre a regra detalhada e a
Investment Policy tem sua própria suíte dedicada em
`test_decision_limit_precedence.py`.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.decision.eligibility import filter_eligible_v3
from backend.app.engines.decision.engine import recommend_v3
from backend.app.engines.decision.inputs import (
    DEFAULT_CONFIG,
    AllocationRuleSignal,
    DecisionInput,
    PolicyLimits,
    PortfolioAggregates,
)
from backend.app.engines.decision.scoring import compute_buy_score_v3


def _candidate(**overrides) -> DecisionInput:
    base = dict(
        ticker="TEST3.SA",
        asset_class="stock",
        lg_score=Decimal("60"),
        confidence=Decimal("1"),
        current_weight=Decimal("0.10"),
    )
    base.update(overrides)
    return DecisionInput(**base)


# --- fallback de fundamentos -------------------------------------------------


def test_fundamentals_uses_individual_pillars_when_available():
    candidate = _candidate(
        quality_score=Decimal("80"),
        valuation_score=Decimal("60"),
        growth_score=Decimal("70"),
        risk_score=Decimal("90"),
    )
    score = compute_buy_score_v3(candidate)
    assert (
        score.lg_norm == (Decimal("80") + Decimal("60") + Decimal("70") + Decimal("90")) / 4 / 100
    )
    assert any("fundamentos (média de" in r for r in score.reasons)


def test_fundamentals_falls_back_to_conviction_score_without_pillars():
    candidate = _candidate(conviction_score=Decimal("75"))
    score = compute_buy_score_v3(candidate)
    assert score.lg_norm == Decimal("0.75")
    assert any("LG Conviction Score" in r for r in score.reasons)


def test_fundamentals_falls_back_to_lg_score_without_conviction():
    candidate = _candidate(lg_score=Decimal("55"))
    score = compute_buy_score_v3(candidate)
    assert score.lg_norm == Decimal("0.55")
    assert any("LG Score" in r for r in score.reasons)


# --- bônus de alocação-alvo multi-dimensão ----------------------------------


def test_allocation_bonus_zero_without_rule_signals():
    candidate = _candidate()
    score = compute_buy_score_v3(candidate)
    assert score.gap == Decimal("0")


def test_allocation_bonus_zero_when_no_underweight_signal():
    candidate = _candidate(
        rule_signals=(AllocationRuleSignal("class", "overweight", 0, False, False),)
    )
    score = compute_buy_score_v3(candidate)
    assert score.gap == Decimal("0")


def test_allocation_bonus_scales_with_priority():
    low = _candidate(
        ticker="A", rule_signals=(AllocationRuleSignal("class", "underweight", 5, True, False),)
    )
    high = _candidate(
        ticker="B", rule_signals=(AllocationRuleSignal("class", "underweight", 15, True, False),)
    )
    assert compute_buy_score_v3(high).gap > compute_buy_score_v3(low).gap


def test_allocation_bonus_picks_best_underweight_among_multiple_dimensions():
    candidate = _candidate(
        rule_signals=(
            AllocationRuleSignal("class", "underweight", 5, True, False),
            AllocationRuleSignal("currency", "underweight", 18, True, False),
            AllocationRuleSignal("country", "overweight", 0, False, False),
        )
    )
    score = compute_buy_score_v3(candidate)
    # A prioridade mais alta é a de "currency" (18 > 5) — a razão em texto
    # (Sprint 31, RC v1.0, Parte 2) traduz a dimensão para português
    # ("moeda"), nunca a chave técnica crua.
    assert any("moeda" in r for r in score.reasons)


# --- bônus de internacionalização -------------------------------------------


def test_international_bonus_zero_for_domestic_asset():
    candidate = _candidate(is_international=False)
    policy = PolicyLimits(target_international_min=Decimal("0.30"))
    aggregates = PortfolioAggregates(international_weight=Decimal("0.05"))
    score = compute_buy_score_v3(candidate, policy=policy, aggregates=aggregates)
    assert any("ativo nacional" in r for r in score.reasons)


def test_international_bonus_applies_when_underweight():
    candidate = _candidate(is_international=True)
    policy = PolicyLimits(target_international_min=Decimal("0.30"))
    aggregates = PortfolioAggregates(international_weight=Decimal("0.05"))
    score = compute_buy_score_v3(candidate, policy=policy, aggregates=aggregates)
    assert any("abaixo da meta mínima" in r for r in score.reasons)


def test_international_bonus_zero_when_already_within_target():
    candidate = _candidate(is_international=True)
    policy = PolicyLimits(target_international_min=Decimal("0.30"))
    aggregates = PortfolioAggregates(international_weight=Decimal("0.40"))
    score = compute_buy_score_v3(candidate, policy=policy, aggregates=aggregates)
    assert any("já dentro da meta" in r for r in score.reasons)


def test_international_bonus_zero_without_policy():
    candidate = _candidate(is_international=True)
    score = compute_buy_score_v3(candidate)
    assert any("sem meta de exposição internacional" in r for r in score.reasons)


# --- escala pela confiança ---------------------------------------------------


def test_score_scaled_down_by_low_confidence():
    high_conf = _candidate(ticker="A", confidence=Decimal("1"))
    low_conf = _candidate(ticker="B", confidence=Decimal("0.3"))
    assert compute_buy_score_v3(low_conf).score < compute_buy_score_v3(high_conf).score
    assert any("escalado pela confiança" in r for r in compute_buy_score_v3(low_conf).reasons)


def test_zero_confidence_zeroes_score():
    candidate = _candidate(confidence=Decimal("0"))
    score = compute_buy_score_v3(candidate)
    assert score.score == Decimal("0")


# --- bloqueio por Investment Policy ------------------------------------------


def test_filter_v3_blocks_asset_above_max_asset_weight():
    # 0.25 fica abaixo do over_concentration_limit padrão (0.30), isolando
    # o bloqueio específico da Investment Policy (max_asset_weight=0.20).
    candidate = _candidate(current_weight=Decimal("0.25"))
    policy = PolicyLimits(max_asset_weight=Decimal("0.20"))
    eligible, ignored = filter_eligible_v3(
        [candidate], set(), DEFAULT_CONFIG, policy=policy, aggregates=None
    )
    assert eligible == []
    assert "peso máximo por ativo" in ignored[0].reason
    assert "venda" not in ignored[0].reason or "não é recomendação" in ignored[0].reason
    assert ignored[0].block_source == "politica_geral"


def test_filter_v3_blocks_crypto_class_over_policy_limit():
    candidate = _candidate(ticker="BTC-USD", asset_class="crypto", current_weight=Decimal("0.03"))
    policy = PolicyLimits(max_crypto_weight=Decimal("0.05"))
    aggregates = PortfolioAggregates(crypto_weight=Decimal("0.10"))
    eligible, ignored = filter_eligible_v3(
        [candidate], set(), DEFAULT_CONFIG, policy=policy, aggregates=aggregates
    )
    assert eligible == []
    assert "crypto" in ignored[0].reason
    assert ignored[0].block_source == "politica_geral"


def test_filter_v3_blocks_fii_class_over_policy_limit():
    candidate = _candidate(ticker="HGLG11.SA", asset_class="fii", current_weight=Decimal("0.02"))
    policy = PolicyLimits(target_fii_max=Decimal("0.15"))
    aggregates = PortfolioAggregates(fii_weight=Decimal("0.20"))
    eligible, ignored = filter_eligible_v3(
        [candidate], set(), DEFAULT_CONFIG, policy=policy, aggregates=aggregates
    )
    assert eligible == []
    assert "fii" in ignored[0].reason


def test_filter_v3_does_not_block_when_no_policy_configured():
    candidate = _candidate(current_weight=Decimal("0.25"))
    eligible, ignored = filter_eligible_v3([candidate], set(), DEFAULT_CONFIG)
    assert eligible == [candidate]
    assert ignored == []


def test_filter_v3_blocks_via_rule_signal_blocked_status():
    candidate = _candidate(
        asset_class="fii",
        rule_signals=(
            AllocationRuleSignal(
                "class",
                "blocked",
                0,
                True,
                True,
                dimension_key="fii",
                current_weight=Decimal("0.344"),
                max_weight=Decimal("0.25"),
            ),
        ),
    )
    eligible, ignored = filter_eligible_v3([candidate], set(), DEFAULT_CONFIG)
    assert eligible == []
    assert "regra detalhada" in ignored[0].reason
    assert "34.4%" in ignored[0].reason
    assert "25.0%" in ignored[0].reason
    assert ignored[0].block_source == "regra_detalhada"


def test_filter_v3_still_applies_v1_blocking_rules():
    candidate = _candidate(current_weight=Decimal("0.40"))  # acima de over_concentration_limit
    eligible, ignored = filter_eligible_v3(
        [candidate], set(), DEFAULT_CONFIG, policy=None, aggregates=None
    )
    assert eligible == []
    assert "sobreconcentrado" in ignored[0].reason
    assert ignored[0].block_source == "sobreconcentracao"


# --- regra de ouro: nunca recomendar venda -----------------------------------


def test_never_recommends_sell_even_when_blocked():
    candidate = _candidate(current_weight=Decimal("0.25"))
    policy = PolicyLimits(max_asset_weight=Decimal("0.20"))
    _, ignored = filter_eligible_v3([candidate], set(), DEFAULT_CONFIG, policy=policy)
    assert "vender" not in ignored[0].reason
    assert "não é recomendação de venda" in ignored[0].reason


def test_recommend_v3_end_to_end_never_suggests_sell():
    candidates = [
        _candidate(ticker="A", current_weight=Decimal("0.05"), lg_score=Decimal("80")),
        _candidate(
            ticker="B",
            asset_class="crypto",
            current_weight=Decimal("0.02"),
            lg_score=Decimal("70"),
        ),
    ]
    policy = PolicyLimits(max_crypto_weight=Decimal("0.05"))
    aggregates = PortfolioAggregates(crypto_weight=Decimal("0.10"))
    result = recommend_v3(candidates, Decimal("1000"), policy=policy, aggregates=aggregates)
    assert result.audit.model_version == "decision_v3"
    all_text = " ".join(result.explanation.split()) + " ".join(result.alerts)
    for ignored in result.ignored:
        all_text += " " + ignored.reason
    assert "vender" not in all_text.lower()


# --- score_breakdown estruturado (Sprint 25, Parte 4) ------------------------


def test_v3_score_breakdown_has_five_factors_including_confidence_row():
    candidate = _candidate(is_international=True)
    policy = PolicyLimits(target_international_min=Decimal("0.30"))
    aggregates = PortfolioAggregates(international_weight=Decimal("0.05"))
    score = compute_buy_score_v3(candidate, policy=policy, aggregates=aggregates)
    labels = [f.label for f in score.factors]
    assert labels == [
        "Fundamentos",
        "Bônus alocação-alvo",
        "Concentração invertida",
        "Bônus internacional",
        "Ajuste por confiança do dado",
    ]
    assert score.factors[-1].weight is None  # escala, não é peso aditivo


def test_v3_score_breakdown_contributions_sum_to_final_score():
    candidate = _candidate(confidence=Decimal("0.6"), is_international=True)
    policy = PolicyLimits(target_international_min=Decimal("0.30"))
    aggregates = PortfolioAggregates(international_weight=Decimal("0.05"))
    score = compute_buy_score_v3(candidate, policy=policy, aggregates=aggregates)
    total = sum((f.contribution for f in score.factors), start=Decimal("0"))
    assert total == score.score


def test_v3_confidence_row_contribution_is_negative_below_full_confidence():
    candidate = _candidate(confidence=Decimal("0.5"))
    score = compute_buy_score_v3(candidate)
    assert score.factors[-1].contribution < Decimal("0")


def test_v3_confidence_row_contribution_is_zero_at_full_confidence():
    candidate = _candidate(confidence=Decimal("1"))
    score = compute_buy_score_v3(candidate)
    assert score.factors[-1].contribution == Decimal("0")


# --- watchlist_reason (Sprint 25, Parte 4) ------------------------------------


def test_recommend_v3_sets_watchlist_reason_only_for_new_candidates():
    held = _candidate(ticker="HELD3.SA", is_new_from_watchlist=False)
    new = _candidate(ticker="NEW3.SA", current_weight=Decimal("0"), is_new_from_watchlist=True)
    result = recommend_v3([held, new], Decimal("1000"))
    by_ticker = {i.ticker: i for i in result.items}
    assert by_ticker["HELD3.SA"].watchlist_reason is None
    assert by_ticker["NEW3.SA"].watchlist_reason is not None
    assert "Watchlist/Radar" in by_ticker["NEW3.SA"].watchlist_reason
    assert "vender" not in by_ticker["NEW3.SA"].watchlist_reason.lower()
