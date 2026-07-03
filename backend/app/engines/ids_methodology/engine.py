"""LG Conviction Score — agregador da IDS Methodology (Sprint 12).

Combina os cinco pilares (Quality/Valuation/Growth/Risk/Capital
Reinvestment) pelos pesos do perfil da classe de ativo (`profile.py`),
no mesmo padrão de agregação do LG Score (`engines/lg_score/engine.py`):
score final 0..100, confiança agregada, classificação e explicação por
pilar.

Este é um score PARALELO ao LG Score, não um substituto: o Decision
Engine continua usando exclusivamente o LG Score nesta sprint. O
Conviction Score é a fundação da metodologia completa de decisão
(Quality/Valuation/Growth/Risk/Capital Reinvestment) — ver
docs/IDS_METHODOLOGY.md para a explicação conceitual.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.ids_methodology.pillars import (
    capital_reinvestment_pillar,
    capital_reinvestment_pillar_v2,
    growth_pillar,
    growth_pillar_v2,
    quality_pillar,
    quality_pillar_v2,
    risk_pillar,
    risk_pillar_v2,
    valuation_pillar,
    valuation_pillar_v2,
)
from backend.app.engines.ids_methodology.profile import weights_for_asset_class
from backend.app.engines.ids_methodology.weights import IdsPillarWeights
from backend.app.engines.lg_score.confidence import confidence_label
from backend.app.engines.lg_score.inputs import ScoreInput
from backend.app.engines.lg_score.normalization import clamp_score
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.growth import GrowthResult
from backend.app.schemas.ids_methodology import ConvictionPillarResult, ConvictionScoreResult
from backend.app.schemas.quality import QualityResult
from backend.app.schemas.risk import RiskResult
from backend.app.schemas.valuation import ValuationResult

MODEL_VERSION = "ids_conviction_v1"
MODEL_VERSION_V2 = "ids_conviction_v2"


def _classify(score: Decimal) -> str:
    """Classificação textual, mesmas faixas do LG Score (Volume 6, seção 11)."""
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


def calculate_conviction_score(
    data: ScoreInput, weights: IdsPillarWeights | None = None
) -> ConvictionScoreResult:
    """Calcula o LG Conviction Score de um ativo.

    `weights` permite sobrescrever o perfil padrão da classe do ativo
    (ex.: simulação/teste); por padrão usa o perfil de `profile.py`.
    """
    resolved_weights = weights if weights is not None else weights_for_asset_class(data.asset_class)
    resolved_weights.validate()

    quality = quality_pillar(data)
    valuation = valuation_pillar(data)
    growth = growth_pillar(data)
    risk = risk_pillar(data)
    capital_reinvestment = capital_reinvestment_pillar(data)

    conviction_score = clamp_score(
        Decimal(str(resolved_weights.quality)) * quality.score
        + Decimal(str(resolved_weights.valuation)) * valuation.score
        + Decimal(str(resolved_weights.growth)) * growth.score
        + Decimal(str(resolved_weights.risk)) * risk.score
        + Decimal(str(resolved_weights.capital_reinvestment)) * capital_reinvestment.score
    )

    confidence = (
        Decimal(str(resolved_weights.quality)) * quality.confidence
        + Decimal(str(resolved_weights.valuation)) * valuation.confidence
        + Decimal(str(resolved_weights.growth)) * growth.confidence
        + Decimal(str(resolved_weights.risk)) * risk.confidence
        + Decimal(str(resolved_weights.capital_reinvestment)) * capital_reinvestment.confidence
    )

    explanation = [
        ConvictionPillarResult(
            name="quality",
            score=quality.score,
            confidence=quality.confidence,
            reasons=quality.reasons,
        ),
        ConvictionPillarResult(
            name="valuation",
            score=valuation.score,
            confidence=valuation.confidence,
            reasons=valuation.reasons,
        ),
        ConvictionPillarResult(
            name="growth", score=growth.score, confidence=growth.confidence, reasons=growth.reasons
        ),
        ConvictionPillarResult(
            name="risk", score=risk.score, confidence=risk.confidence, reasons=risk.reasons
        ),
        ConvictionPillarResult(
            name="capital_reinvestment",
            score=capital_reinvestment.score,
            confidence=capital_reinvestment.confidence,
            reasons=capital_reinvestment.reasons,
        ),
    ]

    return ConvictionScoreResult(
        ticker=data.ticker,
        conviction_score=conviction_score,
        quality=quality.score,
        valuation=valuation.score,
        growth=growth.score,
        risk=risk.score,
        capital_reinvestment=capital_reinvestment.score,
        confidence=confidence,
        confidence_label=confidence_label(confidence),
        classification=_classify(conviction_score),
        model_version=MODEL_VERSION,
        explanation=explanation,
    )


def calculate_conviction_score_v2(
    data: ScoreInput,
    weights: IdsPillarWeights | None = None,
    quality_result: QualityResult | None = None,
    growth_result: GrowthResult | None = None,
    risk_result: RiskResult | None = None,
    valuation_result: ValuationResult | None = None,
    latest_snapshot: FundamentalSnapshotResult | None = None,
) -> ConvictionScoreResult:
    """Calcula o LG Conviction Score v2 de um ativo.

    Usa os resultados reais dos engines de fundamentos (Sprints 14-16)
    quando fornecidos; qualquer resultado ausente ou "indeterminado"
    cai de volta na proxy de preço v1 daquele pilar especificamente
    (nunca do score inteiro) — a razão registrada sempre indica qual
    caminho foi usado. `data` (`ScoreInput`) continua obrigatório: é a
    base da proxy de fallback e da classe do ativo usada nos pesos.
    """
    resolved_weights = weights if weights is not None else weights_for_asset_class(data.asset_class)
    resolved_weights.validate()

    quality = quality_pillar_v2(data, quality_result)
    valuation = valuation_pillar_v2(data, valuation_result)
    growth = growth_pillar_v2(data, growth_result)
    risk = risk_pillar_v2(data, risk_result)
    capital_reinvestment = capital_reinvestment_pillar_v2(data.asset_class, latest_snapshot)

    conviction_score = clamp_score(
        Decimal(str(resolved_weights.quality)) * quality.score
        + Decimal(str(resolved_weights.valuation)) * valuation.score
        + Decimal(str(resolved_weights.growth)) * growth.score
        + Decimal(str(resolved_weights.risk)) * risk.score
        + Decimal(str(resolved_weights.capital_reinvestment)) * capital_reinvestment.score
    )

    confidence = (
        Decimal(str(resolved_weights.quality)) * quality.confidence
        + Decimal(str(resolved_weights.valuation)) * valuation.confidence
        + Decimal(str(resolved_weights.growth)) * growth.confidence
        + Decimal(str(resolved_weights.risk)) * risk.confidence
        + Decimal(str(resolved_weights.capital_reinvestment)) * capital_reinvestment.confidence
    )

    explanation = [
        ConvictionPillarResult(
            name="quality",
            score=quality.score,
            confidence=quality.confidence,
            reasons=quality.reasons,
        ),
        ConvictionPillarResult(
            name="valuation",
            score=valuation.score,
            confidence=valuation.confidence,
            reasons=valuation.reasons,
        ),
        ConvictionPillarResult(
            name="growth", score=growth.score, confidence=growth.confidence, reasons=growth.reasons
        ),
        ConvictionPillarResult(
            name="risk", score=risk.score, confidence=risk.confidence, reasons=risk.reasons
        ),
        ConvictionPillarResult(
            name="capital_reinvestment",
            score=capital_reinvestment.score,
            confidence=capital_reinvestment.confidence,
            reasons=capital_reinvestment.reasons,
        ),
    ]

    return ConvictionScoreResult(
        ticker=data.ticker,
        conviction_score=conviction_score,
        quality=quality.score,
        valuation=valuation.score,
        growth=growth.score,
        risk=risk.score,
        capital_reinvestment=capital_reinvestment.score,
        confidence=confidence,
        confidence_label=confidence_label(confidence),
        classification=_classify(conviction_score),
        model_version=MODEL_VERSION_V2,
        explanation=explanation,
    )
