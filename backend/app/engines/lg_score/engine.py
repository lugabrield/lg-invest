"""LG Score Engine v1 (Volume 6 / Volume 17 §9 / Volume 20 prompt 9).

Engine PURA: recebe um `ScoreInput` já tratado e devolve um
`LGScoreResult` com score final 0..100, as cinco notas parciais,
confiança, classificação e explicação por pilar.

LG_SCORE = 0.35*Q + 0.25*V + 0.20*G + 0.10*R + 0.10*A
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.lg_score.confidence import (
    aggregate_confidence,
    confidence_label,
)
from backend.app.engines.lg_score.inputs import ScoreInput
from backend.app.engines.lg_score.normalization import clamp_score
from backend.app.engines.lg_score.pillars import (
    allocation_pillar,
    growth_pillar,
    quality_pillar,
    risk_pillar,
    valuation_pillar,
)
from backend.app.engines.lg_score.weights import DEFAULT_WEIGHTS, LGScoreWeights
from backend.app.schemas.lg_score import LGScoreResult, PillarResult

MODEL_VERSION = "lg_score_v1"


def _classify(score: Decimal) -> str:
    """Classificação textual conforme faixas do Volume 6, seção 11."""
    if score >= 90:
        return "Exceptional"
    if score >= 80:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 60:
        return "Neutral"
    if score >= 40:
        return "Weak"
    return "Avoid"


def calculate_lg_score(
    data: ScoreInput, weights: LGScoreWeights = DEFAULT_WEIGHTS
) -> LGScoreResult:
    """Calcula o LG Score de um ativo a partir de dados já tratados."""
    weights.validate()

    quality = quality_pillar(data)
    valuation = valuation_pillar(data)
    growth = growth_pillar(data)
    risk = risk_pillar(data)
    allocation = allocation_pillar(data)

    lg_score = clamp_score(
        Decimal(str(weights.quality)) * quality.score
        + Decimal(str(weights.valuation)) * valuation.score
        + Decimal(str(weights.growth)) * growth.score
        + Decimal(str(weights.risk)) * risk.score
        + Decimal(str(weights.allocation)) * allocation.score
    )

    confidence = aggregate_confidence(quality, valuation, growth, risk, allocation, weights)

    explanation = [
        PillarResult(
            name="quality",
            score=quality.score,
            confidence=quality.confidence,
            reasons=quality.reasons,
        ),
        PillarResult(
            name="valuation",
            score=valuation.score,
            confidence=valuation.confidence,
            reasons=valuation.reasons,
        ),
        PillarResult(
            name="growth", score=growth.score, confidence=growth.confidence, reasons=growth.reasons
        ),
        PillarResult(
            name="risk", score=risk.score, confidence=risk.confidence, reasons=risk.reasons
        ),
        PillarResult(
            name="allocation",
            score=allocation.score,
            confidence=allocation.confidence,
            reasons=allocation.reasons,
        ),
    ]

    return LGScoreResult(
        ticker=data.ticker,
        lg_score=lg_score,
        quality=quality.score,
        valuation=valuation.score,
        growth=growth.score,
        risk=risk.score,
        allocation=allocation.score,
        confidence=confidence,
        confidence_label=confidence_label(confidence),
        classification=_classify(lg_score),
        model_version=MODEL_VERSION,
        explanation=explanation,
    )
