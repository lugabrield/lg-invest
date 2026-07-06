"""Target Allocation Engine — comparação pura entre alocação atual e meta.

Recebe a alocação atual por classe (já calculada pelo Portfolio
Engine) e a alocação-alvo configurada pelo usuário (já lida pelo
serviço) e devolve o desvio por classe. Não acessa banco, yfinance nem
Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from backend.app.schemas.target_allocation import (
    AllocationClassDrift,
    AllocationRuleEvaluation,
    TargetAllocationEvaluation,
    TargetAllocationResult,
)

# Tolerância em torno da meta considerada "dentro" (não gera desvio
# acionável) — mesmo espírito dos limiares do Portfolio Diagnostics
# (Sprint 11): constante simples e documentada, não uma otimização.
DRIFT_TOLERANCE = Decimal("0.03")

_ZERO = Decimal("0")


def _status(drift: Decimal) -> str:
    if drift <= -DRIFT_TOLERANCE:
        return "abaixo"
    if drift >= DRIFT_TOLERANCE:
        return "acima"
    return "dentro"


class TargetAllocationEngine:
    """Compara alocação atual x alocação-alvo, classe a classe."""

    def compare(
        self,
        current_allocation: dict[str, Decimal],
        target_allocation: dict[str, Decimal],
    ) -> TargetAllocationResult:
        if not target_allocation:
            return TargetAllocationResult(
                has_target=False,
                reason="nenhuma meta de alocação configurada",
            )

        all_classes = sorted(set(current_allocation) | set(target_allocation))
        classes: list[AllocationClassDrift] = []
        for asset_class in all_classes:
            current_pct = current_allocation.get(asset_class, _ZERO)
            target_pct = target_allocation.get(asset_class, _ZERO)
            drift_pct = current_pct - target_pct
            classes.append(
                AllocationClassDrift(
                    asset_class=asset_class,
                    current_pct=current_pct,
                    target_pct=target_pct,
                    drift_pct=drift_pct,
                    status=_status(drift_pct),
                )
            )

        underweight = [c for c in classes if c.status == "abaixo"]
        most_underweight = (
            min(underweight, key=lambda c: c.drift_pct).asset_class if underweight else None
        )

        return TargetAllocationResult(
            has_target=True,
            classes=classes,
            most_underweight_class=most_underweight,
        )


# --- Target Allocation Engine v2 (Sprint 24, Fase 3) -------------------------
#
# Multiplica a lógica acima para 4 dimensões independentes (classe, moeda,
# país, ativo) e para peso mínimo/alvo/máximo + prioridade manual, mantendo
# o mesmo princípio: puro, sem banco/rede/Streamlit, nunca recomenda venda
# como ação padrão (Buy and Hold).

# Multiplicador sobre `max_weight` a partir do qual um desvio overweight é
# sinalizado como "extremo" no `alert_message` — mesmo assim NUNCA vira uma
# recomendação de venda automática; só um alerta mais forte para o usuário
# decidir por conta própria (ver Volume 18 / regras do usuário: "nunca
# forçar venda como recomendação padrão").
EXTREME_OVERWEIGHT_MULTIPLIER = Decimal("1.5")


@dataclass(frozen=True)
class AllocationRuleInput:
    """Entrada pura para `TargetAllocationRuleEngine.evaluate` — espelha
    `TargetAllocationRule` (banco) sem depender do ORM."""

    dimension_type: str
    dimension_key: str
    min_weight: Decimal | None
    target_weight: Decimal | None
    max_weight: Decimal | None
    priority: int


def _gap_status(
    current_weight: Decimal,
    target_weight: Decimal | None,
    max_weight: Decimal | None,
    *,
    tolerance: Decimal,
) -> str:
    if max_weight is not None and current_weight > max_weight:
        return "blocked"
    if target_weight is None:
        return "neutral"
    gap = current_weight - target_weight
    if gap <= -tolerance:
        return "underweight"
    if gap >= tolerance:
        return "overweight"
    return "neutral"


def _contribution_priority(status: str, gap: Decimal | None, manual_priority: int) -> int:
    """Prioridade final de aporte: nunca prioriza overweight/blocked (Buy and
    Hold — reduzir prioridade em vez de sugerir venda), soma um bônus pela
    magnitude do gap quando underweight, mais a prioridade manual do usuário
    (desempate explícito, nunca calculado pela engine sozinha)."""
    if status in ("overweight", "blocked"):
        return 0
    if status == "underweight" and gap is not None:
        # gap é negativo quando underweight; magnitude em pontos percentuais
        # inteiros (ex.: -0.07 -> 7) soma à prioridade manual do usuário.
        magnitude_bonus = int(abs(gap) * 100)
        return manual_priority + magnitude_bonus
    return manual_priority


def _alert_message(
    dimension_type: str,
    dimension_key: str,
    status: str,
    *,
    current_weight: Decimal,
    target_weight: Decimal | None,
    max_weight: Decimal | None,
    extreme: bool,
) -> str | None:
    label = f"{dimension_type}={dimension_key}"
    if status == "blocked":
        base = (
            f"{label}: peso atual ({current_weight * 100:.1f}%) ultrapassa o máximo "
            f"configurado ({max_weight * 100:.1f}%). Aporte bloqueado nesta dimensão."
        )
        if extreme:
            base += (
                " Desvio é extremo (mais de 1.5x o máximo) — considere revisar manualmente; "
                "a LG INVEST nunca sugere venda automática, mesmo em desvios extremos."
            )
        return base
    if status == "overweight":
        return (
            f"{label}: acima da meta ({current_weight * 100:.1f}% vs. "
            f"{target_weight * 100:.1f}% alvo). Recomendação: pausar novos aportes "
            "aqui, não vender — Buy and Hold prioriza não piorar a concentração, "
            "não reduzir posições existentes."
        )
    if status == "underweight":
        return (
            f"{label}: abaixo da meta ({current_weight * 100:.1f}% vs. "
            f"{target_weight * 100:.1f}% alvo). Candidato a priorizar no próximo aporte."
        )
    return None


class TargetAllocationRuleEngine:
    """Avalia a alocação atual contra regras (`AllocationRuleInput`) em
    até 4 dimensões independentes — classe, moeda, país, ativo. Cada
    dimensão é avaliada isoladamente; a engine nunca mistura, por
    exemplo, o peso de uma classe com o peso de uma moeda na mesma
    conta."""

    def evaluate(
        self,
        current_weights: dict[tuple[str, str], Decimal],
        rules: list[AllocationRuleInput],
        *,
        rebalance_threshold: Decimal = DRIFT_TOLERANCE,
    ) -> TargetAllocationEvaluation:
        if not rules:
            return TargetAllocationEvaluation(
                has_rules=False,
                reason="nenhuma regra de alocação configurada",
            )

        evaluations: list[AllocationRuleEvaluation] = []
        for rule in rules:
            key = (rule.dimension_type, rule.dimension_key)
            current_weight = current_weights.get(key, _ZERO)
            status = _gap_status(
                current_weight,
                rule.target_weight,
                rule.max_weight,
                tolerance=rebalance_threshold,
            )
            gap = current_weight - rule.target_weight if rule.target_weight is not None else None
            extreme = bool(
                rule.max_weight is not None
                and current_weight > rule.max_weight * EXTREME_OVERWEIGHT_MULTIPLIER
            )
            rebalance_required = status in ("overweight", "blocked") or (
                status == "underweight" and gap is not None and abs(gap) > rebalance_threshold
            )
            evaluations.append(
                AllocationRuleEvaluation(
                    dimension_type=rule.dimension_type,
                    dimension_key=rule.dimension_key,
                    current_weight=current_weight,
                    target_weight=rule.target_weight,
                    min_weight=rule.min_weight,
                    max_weight=rule.max_weight,
                    gap_to_target=gap,
                    gap_status=status,
                    contribution_priority=_contribution_priority(status, gap, rule.priority),
                    rebalance_required=rebalance_required,
                    extreme_overweight=extreme,
                    alert_message=_alert_message(
                        rule.dimension_type,
                        rule.dimension_key,
                        status,
                        current_weight=current_weight,
                        target_weight=rule.target_weight,
                        max_weight=rule.max_weight,
                        extreme=extreme,
                    ),
                )
            )

        return TargetAllocationEvaluation(has_rules=True, evaluations=evaluations)
