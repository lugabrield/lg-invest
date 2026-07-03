"""Pilares do LG Conviction Score (IDS Methodology).

v1 (Sprint 12): Quality/Valuation/Growth/Risk reaproveitavam as
proxies do LG Score (`engines/lg_score/pillars.py`), pois a plataforma
ainda não coletava fundamentos. Capital Reinvestment era sempre
neutro/placeholder.

v2 (Sprint 17): com Fundamentals/Quality/Growth/Risk/Valuation Engines
existindo (Sprints 14-16), cada pilar v2 usa o resultado real desses
engines quando disponível (classificação != "indeterminado") e só cai
de volta na proxy de preço v1 quando o dado real não existe — nunca um
degrau silencioso: a razão sempre registra qual caminho foi usado
(Volume 18 §8).

Capital Reinvestment v2 usa a taxa de retenção de lucro (1 − payout
ratio) do snapshot de fundamentos mais recente, quando disponível —
alinhado à filosofia de longo prazo do investidor (priorizar
reinvestimento de capital sobre renda imediata, documentada em
`profile.py`), não uma regra "universalmente correta".
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.lg_score.inputs import ScoreInput
from backend.app.engines.lg_score.normalization import NEUTRAL, clamp_score
from backend.app.engines.lg_score.pillars import PillarScore
from backend.app.engines.lg_score.pillars import growth_pillar as _lg_growth_pillar
from backend.app.engines.lg_score.pillars import quality_pillar as _lg_quality_pillar
from backend.app.engines.lg_score.pillars import risk_pillar as _lg_risk_pillar
from backend.app.engines.lg_score.pillars import valuation_pillar as _lg_valuation_pillar
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.growth import GrowthResult
from backend.app.schemas.quality import QualityResult
from backend.app.schemas.risk import RiskResult
from backend.app.schemas.valuation import ValuationResult

# Mesmo contrato de entrada do LG Score: os dois métodos consomem
# exatamente o mesmo dado de preço (classe do ativo + histórico).
IdsScoreInput = ScoreInput

# Classes com pilar de reinvestimento aplicável (equity puro). FIIs/REITs
# são obrigados por regulação a distribuir a maior parte do resultado —
# payout baixo não indicaria disciplina de reinvestimento, indicaria
# não conformidade — por isso ficam fora deste pilar por ora.
_CAPITAL_REINVESTMENT_CLASSES = ("stock", "etf")

_CONFIDENCE_BY_LABEL = {"alta": Decimal("0.9"), "média": Decimal("0.6"), "baixa": Decimal("0.3")}

_QUALITY_SCORE_BY_CLASSIFICATION = {
    "alta": Decimal("80"),
    "média": Decimal("60"),
    "baixa": Decimal("30"),
}
_GROWTH_SCORE_BY_CLASSIFICATION = {
    "forte": Decimal("80"),
    "moderado": Decimal("60"),
    "fraco": Decimal("30"),
}
_RISK_SCORE_BY_CLASSIFICATION = {
    "baixo": Decimal("80"),
    "médio": Decimal("60"),
    "alto": Decimal("30"),
}
_VALUATION_SCORE_BY_CLASSIFICATION = {
    "barato": Decimal("80"),
    "neutro": Decimal("60"),
    "caro": Decimal("30"),
}


def quality_pillar(data: IdsScoreInput) -> PillarScore:
    """Qualidade v1: mesma proxy do LG Score (classe do ativo + estabilidade de preço)."""
    return _lg_quality_pillar(data)


def valuation_pillar(data: IdsScoreInput) -> PillarScore:
    """Valuation v1: mesma proxy do LG Score (preço atual vs. média histórica do próprio ativo)."""
    return _lg_valuation_pillar(data)


def growth_pillar(data: IdsScoreInput) -> PillarScore:
    """Crescimento v1: mesma proxy do LG Score (CAGR de preço, não de lucro/FCF)."""
    return _lg_growth_pillar(data)


def risk_pillar(data: IdsScoreInput) -> PillarScore:
    """Risco v1: mesma proxy do LG Score (volatilidade + max drawdown)."""
    return _lg_risk_pillar(data)


def capital_reinvestment_pillar(data: IdsScoreInput) -> PillarScore:
    """Reinvestimento de capital v1 (placeholder, Sprint 12) — sempre neutro."""
    return PillarScore(
        score=NEUTRAL,
        confidence=Decimal("0.1"),
        reasons=[
            "dado ausente: reinvestimento de capital requer fundamentos (lucro, "
            "fluxo de caixa, payout) que a plataforma ainda não coleta; usada "
            "neutralidade (50) até o Fundamentals Engine existir."
        ],
    )


def quality_pillar_v2(data: IdsScoreInput, quality_result: QualityResult | None) -> PillarScore:
    """Qualidade v2: usa o Quality Engine (Sprint 16) real quando disponível."""
    if quality_result is None or quality_result.classification == "indeterminado":
        fallback = quality_pillar(data)
        reason = (
            quality_result.reason if quality_result is not None else "Quality Engine não avaliado"
        )
        fallback.reasons = [
            f"fundamentos indisponíveis ({reason}); usada proxy de preço v1"
        ] + fallback.reasons
        return fallback

    score = _QUALITY_SCORE_BY_CLASSIFICATION[quality_result.classification]
    confidence = _CONFIDENCE_BY_LABEL[quality_result.confidence]
    reasons = [
        f"Quality Engine: {quality_result.classification} (confiança {quality_result.confidence})"
    ]
    reasons += [
        f"{m.label}: {m.verdict}" + (f" ({m.value})" if m.value is not None else "")
        for m in quality_result.metrics
    ]
    return PillarScore(score=score, confidence=confidence, reasons=reasons)


def growth_pillar_v2(data: IdsScoreInput, growth_result: GrowthResult | None) -> PillarScore:
    """Crescimento v2: usa o Growth Engine (Sprint 16, CAGR real) quando disponível."""
    if growth_result is None or growth_result.classification == "indeterminado":
        fallback = growth_pillar(data)
        reason = growth_result.reason if growth_result is not None else "Growth Engine não avaliado"
        fallback.reasons = [
            f"CAGR indisponível ({reason}); usada proxy de preço v1"
        ] + fallback.reasons
        return fallback

    score = _GROWTH_SCORE_BY_CLASSIFICATION[growth_result.classification]
    confidence = _CONFIDENCE_BY_LABEL[growth_result.confidence]
    reasons = [
        f"Growth Engine: {growth_result.classification} (confiança {growth_result.confidence})"
    ]
    reasons += [
        f"{m.label}: {m.verdict}" + (f" ({m.value * 100:.1f}%)" if m.value is not None else "")
        for m in growth_result.metrics
    ]
    return PillarScore(score=score, confidence=confidence, reasons=reasons)


def risk_pillar_v2(data: IdsScoreInput, risk_result: RiskResult | None) -> PillarScore:
    """Risco v2: usa o Risk Engine (Sprint 16, dívida/EBITDA + beta) quando disponível."""
    if risk_result is None or risk_result.classification == "indeterminado":
        fallback = risk_pillar(data)
        reason = risk_result.reason if risk_result is not None else "Risk Engine não avaliado"
        fallback.reasons = [
            f"indicadores de risco indisponíveis ({reason}); usada proxy de preço v1"
        ] + fallback.reasons
        return fallback

    score = _RISK_SCORE_BY_CLASSIFICATION[risk_result.classification]
    confidence = _CONFIDENCE_BY_LABEL[risk_result.confidence]
    reasons = [f"Risk Engine: {risk_result.classification} (confiança {risk_result.confidence})"]
    reasons += [
        f"{m.label}: {m.verdict}" + (f" ({m.value})" if m.value is not None else "")
        for m in risk_result.metrics
    ]
    return PillarScore(score=score, confidence=confidence, reasons=reasons)


def valuation_pillar_v2(
    data: IdsScoreInput, valuation_result: ValuationResult | None
) -> PillarScore:
    """Valuation v2: usa o Valuation Engine (Sprint 15, múltiplos) quando disponível."""
    if valuation_result is None or valuation_result.classification == "indeterminado":
        fallback = valuation_pillar(data)
        reason = (
            valuation_result.reason
            if valuation_result is not None
            else "Valuation Engine não avaliado"
        )
        fallback.reasons = [
            f"múltiplos indisponíveis ({reason}); usada proxy de preço v1"
        ] + fallback.reasons
        return fallback

    score = _VALUATION_SCORE_BY_CLASSIFICATION[valuation_result.classification]
    confidence = _CONFIDENCE_BY_LABEL[valuation_result.confidence]
    reasons = [
        f"Valuation Engine: {valuation_result.classification} (confiança {valuation_result.confidence})"
    ]
    reasons += [
        f"{m.label}: {m.verdict}" + (f" ({m.value})" if m.value is not None else "")
        for m in valuation_result.metrics
    ]
    return PillarScore(score=score, confidence=confidence, reasons=reasons)


def capital_reinvestment_pillar_v2(
    asset_class: str, snapshot: FundamentalSnapshotResult | None
) -> PillarScore:
    """Reinvestimento de capital v2: taxa de retenção (1 − payout ratio).

    Só aplicável a `stock`/`etf` (ver módulo). Preferência por maior
    retenção reflete o perfil de longo prazo do investidor documentado
    em `profile.py`, não uma regra universal de "melhor"/"pior".
    """
    if asset_class not in _CAPITAL_REINVESTMENT_CLASSES:
        return PillarScore(
            score=NEUTRAL,
            confidence=Decimal("0.1"),
            reasons=[f"reinvestimento de capital não aplicável à classe '{asset_class}'"],
        )

    if snapshot is None or snapshot.payout_ratio is None:
        return PillarScore(
            score=NEUTRAL,
            confidence=Decimal("0.1"),
            reasons=["dado ausente: payout ratio indisponível; usada neutralidade (50)"],
        )

    retention = Decimal("1") - snapshot.payout_ratio
    score = clamp_score(Decimal("50") + retention * Decimal("50"))
    reasons = [
        f"payout ratio: {snapshot.payout_ratio * 100:.1f}% -> retenção estimada "
        f"{retention * 100:.1f}% -> nota {score:.1f}",
        "prioriza retenção/reinvestimento sobre distribuição imediata, "
        "conforme o perfil de longo prazo do investidor",
    ]
    return PillarScore(score=score, confidence=Decimal("0.7"), reasons=reasons)
