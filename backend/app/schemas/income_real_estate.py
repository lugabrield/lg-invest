"""Schema de saída da Análise de Renda Imobiliária — FIIs/REITs (Sprint 26, Fase 4).

FIIs e REITs não são analisados como empresas operacionais comuns:
nunca recebem DCF (não há reinvestimento de lucro no sentido societário
clássico — a distribuição é o próprio modelo), e P/L não é métrica
relevante (lucro contábil de FII costuma ser distorcido por
reavaliação de ativos, não geração de caixa recorrente). A análise gira
em torno de P/VP, Dividend Yield e a ESTABILIDADE desse yield ao longo
do tempo — um yield alto só é, `atrativo` se for consistente com o
histórico do próprio ativo, nunca só porque o número do trimestre é alto
(Volume — "não usar P/L como métrica principal", "priorizar P/VP e DY").

Este motor NUNCA gera recomendação de compra/venda.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

STATUS_ATTRACTIVE = "atrativo"
STATUS_NEUTRAL = "neutro"
STATUS_UNATTRACTIVE = "pouco_atrativo"
STATUS_INDETERMINATE = "indeterminado"
STATUSES = (STATUS_ATTRACTIVE, STATUS_NEUTRAL, STATUS_UNATTRACTIVE, STATUS_INDETERMINATE)

DY_STABILITY_STABLE = "estável"
DY_STABILITY_UNSTABLE = "instável"
DY_STABILITY_INDETERMINATE = "indeterminado"

CONFIDENCE_LEVELS = ("alta", "média", "baixa")

INSUFFICIENT_DATA_MESSAGE = "Dados insuficientes para estimar valor justo com confiança."


class IncomeRealEstateAnalysisResult(BaseModel):
    """Análise de FII/REIT — nunca uma faixa de valor justo (não há DCF
    aqui), e sim uma leitura combinada de P/VP + DY + estabilidade."""

    ticker: str
    asset_class: str  # "fii" | "reit"

    status: str = STATUS_INDETERMINATE  # ver STATUSES

    pvp: Decimal | None = None
    dividend_yield: Decimal | None = None
    dy_own_history_average: Decimal | None = None
    dy_stability: str = DY_STABILITY_INDETERMINATE
    dy_stability_reason: str | None = None

    confidence: str = "baixa"  # ver CONFIDENCE_LEVELS
    warnings: list[str] = []
    methodology: list[str] = []  # ex.: "pvp", "dividend_yield", "dy_stability"
    reason: str | None = None  # motivo geral quando indeterminado/fora de escopo
