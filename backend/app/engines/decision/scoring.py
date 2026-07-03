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

from backend.app.engines.decision.inputs import DecisionInput

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
