"""Schema de saída do Capital Reinvestment Engine v1 (Sprint 21).

Mesmo padrão de Quality/Growth/Risk/Valuation: classificação +
confiança + razões explícitas, nunca um número sem explicação. Difere
dos outros engines por também expor `score` (0..100) diretamente — a
taxa de retenção de lucro (1 − payout ratio) é um indicador contínuo,
então a classificação em faixas (forte/moderada/fraca) é só uma leitura
resumida; o LG Conviction Score usa `score` quando disponível para não
perder a granularidade da métrica.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

REINVESTMENT_CLASSIFICATIONS = ("forte", "moderado", "fraco", "indeterminado", "nao_aplicavel")


class ReinvestmentMetricVerdict(BaseModel):
    field: str
    label: str
    value: Decimal | None = None
    verdict: str
    reason: str | None = None


class ReinvestmentResult(BaseModel):
    """Classificação de capacidade/disciplina de reinvestimento de capital de um ativo."""

    ticker: str
    asset_class: str
    classification: str = "indeterminado"  # ver REINVESTMENT_CLASSIFICATIONS
    score: Decimal | None = None  # 0..100, quando calculável
    metrics: list[ReinvestmentMetricVerdict] = []
    confidence: str = "baixa"  # "alta" | "média" | "baixa"
    reason: str | None = None
