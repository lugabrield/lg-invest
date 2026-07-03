"""Valuation Engine v1 — classificação por múltiplos estáticos (pura).

Recebe o snapshot de fundamentos mais recente de um ativo (já
carregado pelo serviço) e devolve um `ValuationResult`. Não acessa
banco, yfinance nem Streamlit. Ausência de múltiplo, classe sem
múltiplos aplicáveis ou nenhum snapshot disponível nunca viram erro —
viram veredito "indeterminado" com razão explícita (Volume 18 §8).
"""

from __future__ import annotations

from backend.app.engines.valuation.thresholds import (
    NOT_APPLICABLE_CLASSES,
    bands_for_asset_class,
)
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.valuation import MetricVerdict, ValuationResult

_VERDICT_WEIGHTS = {"barato": -1, "neutro": 0, "caro": 1}


def _overall_classification(verdicts: list[MetricVerdict]) -> str:
    scored = [v for v in verdicts if v.verdict in _VERDICT_WEIGHTS]
    if not scored:
        return "indeterminado"
    total = sum(_VERDICT_WEIGHTS[v.verdict] for v in scored)
    if total < 0:
        return "barato"
    if total > 0:
        return "caro"
    return "neutro"


class ValuationEngine:
    """Classifica o valuation de um ativo a partir de múltiplos e bandas fixas."""

    def evaluate(
        self,
        ticker: str,
        asset_class: str,
        snapshot: FundamentalSnapshotResult | None,
    ) -> ValuationResult:
        if asset_class in NOT_APPLICABLE_CLASSES:
            return ValuationResult(
                ticker=ticker,
                asset_class=asset_class,
                classification="indeterminado",
                confidence="baixa",
                reason=f"classe '{asset_class}' sem múltiplos de empresa aplicáveis",
            )

        bands = bands_for_asset_class(asset_class)
        if not bands:
            return ValuationResult(
                ticker=ticker,
                asset_class=asset_class,
                classification="indeterminado",
                confidence="baixa",
                reason=f"nenhuma banda de valuation definida para a classe '{asset_class}'",
            )

        if snapshot is None:
            return ValuationResult(
                ticker=ticker,
                asset_class=asset_class,
                classification="indeterminado",
                confidence="baixa",
                reason="nenhum snapshot de fundamentos disponível",
            )

        verdicts: list[MetricVerdict] = []
        for band in bands:
            value = getattr(snapshot, band.field, None)
            if value is None:
                verdicts.append(
                    MetricVerdict(
                        field=band.field,
                        label=band.label,
                        value=None,
                        verdict="indeterminado",
                        reason=f"{band.label} indisponível para {ticker}",
                    )
                )
                continue
            verdicts.append(
                MetricVerdict(
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

        return ValuationResult(
            ticker=ticker,
            asset_class=asset_class,
            classification=_overall_classification(verdicts),
            metrics=verdicts,
            confidence=confidence,
        )
