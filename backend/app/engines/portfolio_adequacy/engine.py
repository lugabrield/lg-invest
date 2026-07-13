"""Portfolio Adequacy Engine — orquestração pura (Sprint 26, Fase 5).

ETF, cripto (BTC) e Tesouro Direto (`asset_class` "bond") não recebem
valuation tradicional neste projeto (ver docstring de
`schemas/portfolio_adequacy.py`). Este engine não recalcula pesos nem
regras — reaproveita, literalmente, o resultado já computado pelo Target
Allocation Engine v2 (`engines/target_allocation/engine.py::
TargetAllocationRuleEngine`), filtrado para a dimensão "asset" (regra
específica do ticker) e "class" (regra da classe), e empacota isso no
mesmo formato usado pelas outras análises por ativo (Valuation Engine
2.0, Análise de Renda Imobiliária) para a UI conseguir mostrar um card
consistente mesmo quando não há valuation tradicional.

Precedência: regra de ativo específica > regra de classe — mesmo
espírito de `engines/target_allocation/precedence.py` (regra mais
específica vence). Nunca recomenda compra/venda: qualquer
`alert_message` já vem pronto do Target Allocation Engine v2, que segue
a mesma disciplina Buy and Hold do resto do projeto.
"""

from __future__ import annotations

from backend.app.schemas.portfolio_adequacy import (
    EVALUATED_DIMENSION_ASSET,
    EVALUATED_DIMENSION_CLASS,
    PortfolioAdequacyResult,
)
from backend.app.schemas.target_allocation import AllocationRuleEvaluation

_APPLICABLE_ASSET_CLASSES = ("etf", "crypto", "bond")

_METHODOLOGY_TARGET_ALLOCATION_RULE = "target_allocation_rule"


class PortfolioAdequacyEngine:
    """Adequação de ETF/cripto/Tesouro à política de alocação — nunca valuation."""

    def evaluate(
        self,
        ticker: str,
        asset_class: str,
        asset_evaluation: AllocationRuleEvaluation | None,
        class_evaluation: AllocationRuleEvaluation | None,
    ) -> PortfolioAdequacyResult:
        if asset_class not in _APPLICABLE_ASSET_CLASSES:
            return PortfolioAdequacyResult(
                ticker=ticker,
                asset_class=asset_class,
                reason=(
                    f"classe '{asset_class}' fora do escopo desta análise (cobre apenas "
                    "ETF, cripto e Tesouro Direto — Sprint 26, Fase 5)"
                ),
            )

        effective = asset_evaluation if asset_evaluation is not None else class_evaluation
        if effective is None:
            return PortfolioAdequacyResult(
                ticker=ticker,
                asset_class=asset_class,
                reason=(
                    "nenhuma regra de alocação configurada para este ativo nem para a "
                    f"classe '{asset_class}' — configure uma meta em Configurações para "
                    "ver a adequação desta posição"
                ),
            )

        is_asset_level = effective is asset_evaluation
        dimension = EVALUATED_DIMENSION_ASSET if is_asset_level else EVALUATED_DIMENSION_CLASS
        confidence = "alta" if is_asset_level else "média"

        warnings: list[str] = []
        if not is_asset_level:
            warnings.append(
                f"Nenhuma regra específica para o ticker '{ticker}' — usando a regra da "
                f"classe '{asset_class}' como aproximação."
            )

        return PortfolioAdequacyResult(
            ticker=ticker,
            asset_class=asset_class,
            adequacy_status=effective.gap_status,
            evaluated_dimension=dimension,
            current_weight=effective.current_weight,
            target_weight=effective.target_weight,
            min_weight=effective.min_weight,
            max_weight=effective.max_weight,
            gap_to_target=effective.gap_to_target,
            rebalance_required=effective.rebalance_required,
            extreme_overweight=effective.extreme_overweight,
            alert_message=effective.alert_message,
            class_current_weight=(
                class_evaluation.current_weight if class_evaluation is not None else None
            ),
            class_target_weight=(
                class_evaluation.target_weight if class_evaluation is not None else None
            ),
            confidence=confidence,
            warnings=warnings,
            methodology=[_METHODOLOGY_TARGET_ALLOCATION_RULE],
        )
