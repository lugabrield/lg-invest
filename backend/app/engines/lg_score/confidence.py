"""Confidence Score do LG Score (Volume 6, seção 12).

No v1 a confiança agrega a qualidade dos dados disponíveis por pilar.
A versão completa do Volume 6 combina data quality, concordância entre
modelos, profundidade histórica, previsibilidade e estabilidade de
premissas — itens que dependem de fundamentos ainda não coletados.

Aqui usamos a média ponderada das confianças locais dos pilares,
seguindo os mesmos pesos do score, para que um pilar importante com
dado fraco reduza a confiança final de forma proporcional.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.lg_score.pillars import PillarScore
from backend.app.engines.lg_score.weights import LGScoreWeights


def aggregate_confidence(
    quality: PillarScore,
    valuation: PillarScore,
    growth: PillarScore,
    risk: PillarScore,
    allocation: PillarScore,
    weights: LGScoreWeights,
) -> Decimal:
    """Confiança final (0..1) como média ponderada das confianças locais."""
    total = (
        Decimal(str(weights.quality)) * quality.confidence
        + Decimal(str(weights.valuation)) * valuation.confidence
        + Decimal(str(weights.growth)) * growth.confidence
        + Decimal(str(weights.risk)) * risk.confidence
        + Decimal(str(weights.allocation)) * allocation.confidence
    )
    return total


def confidence_label(confidence: Decimal) -> str:
    """Rótulo de confiança conforme faixas do Volume 6, seção 12."""
    pct = confidence * Decimal("100")
    if pct > Decimal("80"):
        return "Alta"
    if pct >= Decimal("60"):
        return "Média"
    return "Baixa"
