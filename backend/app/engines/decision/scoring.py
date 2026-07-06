"""Score de compra do Decision Engine v1 (Volume 17, seção 10).

score_compra = 0.50 * lg_score_norm
             + 0.30 * gap_alocacao
             + 0.20 * penalidade_concentracao_invertida

- lg_score_norm: LG Score / 100 (0..1).
- gap_alocacao: max(0, peso_alvo - peso_atual); 0 quando não há alvo.
- penalidade_concentracao_invertida: 1 - peso_atual (quanto menor o peso
  atual, maior o bônus -> favorece subalocados e penaliza concentrados).

Resultado entre 0 e 1. Diferente do LG Score: o LG Score mede a
qualidade estrutural; este score responde se o ativo deve receber
dinheiro AGORA.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.app.engines.decision.inputs import DecisionInput, PolicyLimits, PortfolioAggregates

W_LG = Decimal("0.50")
W_GAP = Decimal("0.30")
W_CONC = Decimal("0.20")


@dataclass
class BuyScore:
    ticker: str
    score: Decimal  # 0..1
    lg_norm: Decimal
    gap: Decimal
    concentration_inverted: Decimal
    reasons: list[str]


def _allocation_gap(data: DecisionInput) -> Decimal:
    if data.target_weight is None:
        return Decimal("0")
    gap = data.target_weight - data.current_weight
    return gap if gap > 0 else Decimal("0")


def compute_buy_score(data: DecisionInput) -> BuyScore:
    lg_norm = data.lg_score / Decimal("100")
    gap = _allocation_gap(data)
    conc_inv = Decimal("1") - data.current_weight

    score = W_LG * lg_norm + W_GAP * gap + W_CONC * conc_inv

    reasons = [
        f"LG Score {data.lg_score:.1f} (normalizado {lg_norm:.2f}, peso 0.50)",
    ]
    if data.target_weight is not None:
        reasons.append(f"gap de alocação {gap * 100:+.1f}% vs. alvo (peso 0.30)")
    else:
        reasons.append("sem peso-alvo definido: gap de alocação = 0")
    reasons.append(
        f"concentração invertida {conc_inv:.2f} (peso atual {data.current_weight * 100:.1f}%, peso 0.20)"
    )

    return BuyScore(
        ticker=data.ticker,
        score=score,
        lg_norm=lg_norm,
        gap=gap,
        concentration_inverted=conc_inv,
        reasons=reasons,
    )


# --- Decision Engine 2.0 (Sprint 18) ---------------------------------------
#
# score_compra_v2 = 0.40 * qualidade_norm
#                  + 0.30 * bonus_classe_subalocada
#                  + 0.30 * penalidade_concentracao_invertida
#
# - qualidade_norm: LG Conviction Score v2 (Sprint 17) / 100 quando
#   disponível; cai para o LG Score (mesma proxy do v1) quando o
#   Conviction Score não pôde ser calculado — nunca um valor inventado.
# - bonus_classe_subalocada: quanto mais a CLASSE do ativo está abaixo da
#   meta de alocação configurada (Sprint 17), maior o bônus; 0 quando a
#   classe está no alvo ou acima, e 0 quando não há meta configurada
#   (nunca penaliza por falta de meta, só reforça quando há uma).
# - penalidade_concentracao_invertida: igual ao v1 (favorece ativos com
#   peso atual menor na carteira).
#
# Pesos somam 1.0, mas não são a mesma fórmula do v1 — refletem a
# disponibilidade de sinais reais de fundamentos e alocação-alvo que o
# v1 não tinha.

W_QUALITY_V2 = Decimal("0.40")
W_CLASS_GAP_V2 = Decimal("0.30")
W_CONC_V2 = Decimal("0.30")

_MAX_CLASS_GAP_BONUS = Decimal("1")  # satura o bônus em 100 p.p. de subalocação


def _quality_norm_v2(data: DecisionInput) -> tuple[Decimal, str]:
    if data.conviction_score is not None:
        return data.conviction_score / Decimal("100"), (
            f"LG Conviction Score {data.conviction_score:.1f} (normalizado "
            f"{data.conviction_score / Decimal('100'):.2f}, peso {W_QUALITY_V2})"
        )
    lg_norm = data.lg_score / Decimal("100")
    return lg_norm, (
        f"Conviction Score indisponível; usado LG Score {data.lg_score:.1f} "
        f"(normalizado {lg_norm:.2f}, peso {W_QUALITY_V2})"
    )


def _class_gap_bonus_v2(data: DecisionInput) -> tuple[Decimal, str]:
    if data.class_drift_pct is None:
        return Decimal("0"), "sem meta de alocação configurada: bônus de classe = 0"
    if data.class_drift_pct >= 0:
        return Decimal("0"), (
            f"classe '{data.asset_class}' não está subalocada "
            f"(desvio {data.class_drift_pct * 100:+.1f}%): bônus = 0"
        )
    bonus = min(_MAX_CLASS_GAP_BONUS, -data.class_drift_pct)
    return bonus, (
        f"classe '{data.asset_class}' subalocada em {-data.class_drift_pct * 100:.1f}% "
        f"vs. meta (peso {W_CLASS_GAP_V2})"
    )


def compute_buy_score_v2(data: DecisionInput) -> BuyScore:
    """Score de compra v2: Conviction Score + desvio de alocação por classe.

    Reaproveita `BuyScore` (mesma forma de dado do v1) para não duplicar
    schema; `lg_norm`/`gap` guardam os componentes v2 correspondentes
    (qualidade e bônus de classe) para manter compatibilidade estrutural.
    """
    quality_norm, quality_reason = _quality_norm_v2(data)
    class_bonus, class_reason = _class_gap_bonus_v2(data)
    conc_inv = Decimal("1") - data.current_weight

    score = W_QUALITY_V2 * quality_norm + W_CLASS_GAP_V2 * class_bonus + W_CONC_V2 * conc_inv

    reasons = [
        quality_reason,
        class_reason,
        f"concentração invertida {conc_inv:.2f} (peso atual "
        f"{data.current_weight * 100:.1f}%, peso {W_CONC_V2})",
    ]

    return BuyScore(
        ticker=data.ticker,
        score=score,
        lg_norm=quality_norm,
        gap=class_bonus,
        concentration_inverted=conc_inv,
        reasons=reasons,
    )


# --- Decision Engine 3.0 (Sprint 24, Fase 4) --------------------------------
#
# score_compra_v3 = [ W_FUND  * fundamentos_norm
#                    + W_ALLOC * bonus_alocacao_multi_dimensao
#                    + W_CONC  * penalidade_concentracao_invertida
#                    + W_INTL  * bonus_internacionalizacao ]
#                  * fator_confianca
#
# - fundamentos_norm: média ponderada de quality/valuation/growth/risk
#   (todos 0..100, "maior é melhor" — inclusive risk). Cai para
#   conviction_score quando os pilares não estão disponíveis, e para
#   lg_score quando nem o conviction_score está — nunca um valor
#   inventado, sempre o melhor sinal disponível, com a razão registrada.
# - bonus_alocacao_multi_dimensao: maior prioridade de aporte entre os
#   `rule_signals` aplicáveis (classe/moeda/país/ativo) do Target
#   Allocation Rule Engine v2, normalizada; 0 quando não há regra
#   configurada para nenhuma dimensão do candidato.
# - penalidade_concentracao_invertida: igual ao v1/v2.
# - bonus_internacionalizacao: só ativos internacionais (`is_international`)
#   recebem bônus, e só quando a carteira está abaixo de
#   `policy.target_international_min` — nunca penaliza ativos nacionais.
# - fator_confianca: multiplica o score pela `confidence` do ativo (0..1)
#   — dado de baixa confiança reduz o score diretamente, não só gera um
#   alerta (regra explícita do usuário: "se confiança baixa, reduzir
#   score").
#
# Pesos somam 1.0 antes do fator de confiança.

W_FUND_V3 = Decimal("0.40")
W_ALLOC_V3 = Decimal("0.25")
W_CONC_V3 = Decimal("0.20")
W_INTL_V3 = Decimal("0.15")

_MAX_ALLOC_BONUS_V3 = Decimal("1")
# Normaliza a prioridade de aporte (inteiro, sem teto definido pelo
# usuário) para 0..1 — saturando em 20 pontos de prioridade, que já
# representa um gap de alocação bem acima da tolerância padrão.
_ALLOC_PRIORITY_SATURATION_V3 = Decimal("20")


def _fundamentals_norm_v3(data: DecisionInput) -> tuple[Decimal, list[str]]:
    pillars = {
        "quality": data.quality_score,
        "valuation": data.valuation_score,
        "growth": data.growth_score,
        "risk": data.risk_score,
    }
    available = {name: value for name, value in pillars.items() if value is not None}
    if available:
        avg = sum(available.values(), start=Decimal("0")) / Decimal(len(available))
        reasons = [f"{name} {value:.1f}/100" for name, value in available.items()]
        return avg / Decimal("100"), [
            "fundamentos (média de " + ", ".join(reasons) + f", peso {W_FUND_V3})"
        ]
    if data.conviction_score is not None:
        return data.conviction_score / Decimal("100"), [
            f"pilares individuais indisponíveis; usado LG Conviction Score "
            f"{data.conviction_score:.1f} (peso {W_FUND_V3})"
        ]
    return data.lg_score / Decimal("100"), [
        f"conviction score indisponível; usado LG Score {data.lg_score:.1f} " f"(peso {W_FUND_V3})"
    ]


def _allocation_bonus_v3(data: DecisionInput) -> tuple[Decimal, str]:
    underweight_signals = [s for s in data.rule_signals if s.gap_status == "underweight"]
    if not underweight_signals:
        if data.rule_signals:
            return Decimal("0"), (
                "sem dimensão underweight nas regras de alocação-alvo aplicáveis: "
                "bônus de alocação = 0"
            )
        return Decimal("0"), "sem regra de alocação-alvo configurada: bônus de alocação = 0"

    best = max(underweight_signals, key=lambda s: s.contribution_priority)
    normalized = min(
        _MAX_ALLOC_BONUS_V3,
        Decimal(best.contribution_priority) / _ALLOC_PRIORITY_SATURATION_V3,
    )
    return normalized, (
        f"underweight na dimensão '{best.dimension_type}' (prioridade "
        f"{best.contribution_priority}, peso {W_ALLOC_V3})"
    )


def _international_bonus_v3(
    data: DecisionInput, policy: PolicyLimits | None, aggregates: PortfolioAggregates | None
) -> tuple[Decimal, str]:
    if not data.is_international:
        return Decimal("0"), "ativo nacional: bônus de internacionalização = 0"
    if policy is None or policy.target_international_min is None or aggregates is None:
        return Decimal("0"), (
            "sem meta de exposição internacional configurada na política: bônus = 0"
        )
    gap = policy.target_international_min - aggregates.international_weight
    if gap <= 0:
        return Decimal("0"), (
            f"exposição internacional já dentro da meta "
            f"({aggregates.international_weight * 100:.1f}% >= "
            f"{policy.target_international_min * 100:.1f}%): bônus = 0"
        )
    normalized = min(Decimal("1"), gap)
    return normalized, (
        f"exposição internacional abaixo da meta mínima da política "
        f"({aggregates.international_weight * 100:.1f}% < "
        f"{policy.target_international_min * 100:.1f}%), peso {W_INTL_V3}"
    )


def compute_buy_score_v3(
    data: DecisionInput,
    policy: PolicyLimits | None = None,
    aggregates: PortfolioAggregates | None = None,
) -> BuyScore:
    """Score de compra v3: fundamentos (quality/valuation/growth/risk) +
    bônus de alocação-alvo multi-dimensão + concentração + bônus de
    internacionalização, com o resultado final escalado pela confiança do
    dado (Sprint 24, Fase 4). Nunca recomenda venda — bloqueios (política,
    Target Allocation Rule Engine) são tratados em `filter_eligible_v3`,
    antes de a engine sequer pontuar o candidato."""
    fundamentals_norm, fundamentals_reasons = _fundamentals_norm_v3(data)
    alloc_bonus, alloc_reason = _allocation_bonus_v3(data)
    conc_inv = Decimal("1") - data.current_weight
    intl_bonus, intl_reason = _international_bonus_v3(data, policy, aggregates)

    raw_score = (
        W_FUND_V3 * fundamentals_norm
        + W_ALLOC_V3 * alloc_bonus
        + W_CONC_V3 * conc_inv
        + W_INTL_V3 * intl_bonus
    )
    score = raw_score * data.confidence

    reasons = list(fundamentals_reasons)
    reasons.append(alloc_reason)
    reasons.append(
        f"concentração invertida {conc_inv:.2f} (peso atual "
        f"{data.current_weight * 100:.1f}%, peso {W_CONC_V3})"
    )
    reasons.append(intl_reason)
    reasons.append(
        f"score final escalado pela confiança do dado ({data.confidence:.2f}) — "
        f"{raw_score:.3f} -> {score:.3f}"
    )

    return BuyScore(
        ticker=data.ticker,
        score=score,
        lg_norm=fundamentals_norm,
        gap=alloc_bonus,
        concentration_inverted=conc_inv,
        reasons=reasons,
    )
