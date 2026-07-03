"""Growth Engine v1 — classificação de crescimento por CAGR (pura).

Recebe a análise de fundamentos já calculada pelo Fundamentals Engine
(`FundamentalsAnalysisResult`, Sprint 14) e devolve um `GrowthResult`.
Não acessa banco, yfinance nem Streamlit. CAGR ausente (histórico
insuficiente, valores não positivos etc.) nunca vira erro — vira
veredito "indeterminado" com a razão já produzida pelo Fundamentals
Engine (Volume 18 §8).
"""

from __future__ import annotations

from backend.app.engines.growth.thresholds import GROWTH_BANDS
from backend.app.schemas.fundamentals_analysis import FundamentalsAnalysisResult
from backend.app.schemas.growth import GrowthMetricVerdict, GrowthResult

_VERDICT_WEIGHTS = {"forte": -1, "moderada": 0, "fraca": 1}


def _overall_classification(verdicts: list[GrowthMetricVerdict]) -> str:
    scored = [v for v in verdicts if v.verdict in _VERDICT_WEIGHTS]
    if not scored:
        return "indeterminado"
    total = sum(_VERDICT_WEIGHTS[v.verdict] for v in scored)
    if total < 0:
        return "forte"
    if total > 0:
        return "fraco"
    return "moderado"


class GrowthEngine:
    """Classifica o crescimento de um ativo a partir do CAGR já calculado."""

    def evaluate(self, ticker: str, analysis: FundamentalsAnalysisResult) -> GrowthResult:
        if analysis.periods_used == 0:
            return GrowthResult(
                ticker=ticker,
                classification="indeterminado",
                confidence="baixa",
                reason=analysis.reason or "nenhum snapshot de fundamentos disponível",
            )

        verdicts: list[GrowthMetricVerdict] = []
        for band in GROWTH_BANDS:
            value = getattr(analysis, band.field, None)
            reason = getattr(analysis, f"{band.field}_reason", None)
            if value is None:
                verdicts.append(
                    GrowthMetricVerdict(
                        field=band.field,
                        label=band.label,
                        value=None,
                        verdict="indeterminado",
                        reason=reason or f"{band.label} não calculável",
                    )
                )
                continue
            verdicts.append(
                GrowthMetricVerdict(
                    field=band.field,
                    label=band.label,
                    value=value,
                    verdict=band.classify(value),
                )
            )

        available = [v for v in verdicts if v.verdict != "indeterminado"]
        if not available:
            confidence = "baixa"
        elif len(available) < len(verdicts):
            confidence = "média"
        else:
            confidence = "alta"

        return GrowthResult(
            ticker=ticker,
            classification=_overall_classification(verdicts),
            metrics=verdicts,
            confidence=confidence,
        )
