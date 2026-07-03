"""Target Allocation Engine — comparação pura entre alocação atual e meta.

Recebe a alocação atual por classe (já calculada pelo Portfolio
Engine) e a alocação-alvo configurada pelo usuário (já lida pelo
serviço) e devolve o desvio por classe. Não acessa banco, yfinance nem
Streamlit.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.schemas.target_allocation import AllocationClassDrift, TargetAllocationResult

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
