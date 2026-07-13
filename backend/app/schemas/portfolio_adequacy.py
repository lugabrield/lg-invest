"""Schema de saída da Adequação de Carteira — ETF/BTC/Tesouro (Sprint 26, Fase 5).

ETFs, cripto (BTC) e Tesouro Direto (`asset_class` "bond") não têm
valuation tradicional aplicável neste projeto: não há DCF, P/L, P/VP nem
Graham para eles (ETF/cripto não têm demonstrações financeiras
societárias comparáveis; Tesouro Direto é renda fixa pública, precificada
por curva de juros, não por múltiplos de empresa). Em vez de fabricar uma
nota de "preço justo" sem dado real por trás — o que violaria "nunca
inventar dado" —, esta análise responde a uma pergunta diferente e
igualmente central ao objetivo da LG INVEST: "esta posição está adequada
à minha política de alocação?", reaproveitando o Target Allocation
Engine v2 já existente (`engines/target_allocation/engine.py`, Sprint
24), nunca recalculando pesos por conta própria.

Nunca gera recomendação de compra/venda — o `alert_message` embutido
(quando existe) já vem pronto do Target Allocation Engine v2, que segue
a mesma disciplina Buy and Hold do resto do projeto (nunca sugere
vender, só pausar aportes ou sinalizar revisão manual).
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

VALUATION_NOT_APPLICABLE_MESSAGE = (
    "Esta classe de ativo não tem valuation tradicional (P/L, P/VP, DCF) aplicável "
    "neste projeto. A análise abaixo é de adequação à política de alocação, não de "
    "preço justo."
)

# Mesmos valores de `schemas/target_allocation.py::GAP_STATUSES`, reexportados
# aqui para quem consome só este schema não precisar importar o de lá — mais
# "indeterminado", específico desta análise (sem regra de alocação configurada
# nem para o ativo, nem para a classe).
ADEQUACY_STATUS_UNDERWEIGHT = "underweight"
ADEQUACY_STATUS_NEUTRAL = "neutral"
ADEQUACY_STATUS_OVERWEIGHT = "overweight"
ADEQUACY_STATUS_BLOCKED = "blocked"
ADEQUACY_STATUS_INDETERMINATE = "indeterminado"
ADEQUACY_STATUSES = (
    ADEQUACY_STATUS_UNDERWEIGHT,
    ADEQUACY_STATUS_NEUTRAL,
    ADEQUACY_STATUS_OVERWEIGHT,
    ADEQUACY_STATUS_BLOCKED,
    ADEQUACY_STATUS_INDETERMINATE,
)

CONFIDENCE_LEVELS = ("alta", "média", "baixa")

# Qual dimensão do Target Allocation Engine v2 foi usada para avaliar este
# ativo — regra específica do ticker (mais confiável) ou regra da classe
# (aproximação, quando não há regra própria do ativo).
EVALUATED_DIMENSION_ASSET = "asset"
EVALUATED_DIMENSION_CLASS = "class"


class PortfolioAdequacyResult(BaseModel):
    """Adequação de UM ativo (ETF/cripto/Tesouro) à política de alocação
    — nunca uma faixa de valor justo, nunca uma recomendação de compra
    ou venda."""

    ticker: str
    asset_class: str

    valuation_applicable: bool = False
    valuation_note: str = VALUATION_NOT_APPLICABLE_MESSAGE

    adequacy_status: str = ADEQUACY_STATUS_INDETERMINATE
    evaluated_dimension: str | None = None  # ver EVALUATED_DIMENSION_*

    current_weight: Decimal | None = None
    target_weight: Decimal | None = None
    min_weight: Decimal | None = None
    max_weight: Decimal | None = None
    gap_to_target: Decimal | None = None
    rebalance_required: bool = False
    extreme_overweight: bool = False
    alert_message: str | None = None

    # Peso da CLASSE inteira (não só deste ativo) — contexto adicional
    # mesmo quando a avaliação efetiva usou a regra de ativo específica.
    class_current_weight: Decimal | None = None
    class_target_weight: Decimal | None = None

    confidence: str = "baixa"  # ver CONFIDENCE_LEVELS
    warnings: list[str] = []
    methodology: list[str] = []
    reason: str | None = None  # motivo geral quando indeterminado/fora de escopo
