"""Quality Engine v1 — classificação por indicadores estáticos (pura).

Recebe o snapshot de fundamentos mais recente de um ativo (já
carregado pelo serviço) e devolve um `QualityResult`. Não acessa banco,
yfinance nem Streamlit. Ausência de indicador, classe fora do escopo ou
nenhum snapshot disponível nunca viram erro — viram veredito
"indeterminado" com razão explícita (Volume 18 §8).
"""

from __future__ import annotations

from backend.app.engines.quality.thresholds import APPLICABLE_CLASSES, QUALITY_BANDS
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.quality import QualityMetricVerdict, QualityResult

_VERDICT_WEIGHTS = {"forte": -1, "média": 0, "fraca": 1}


def _overall_classification(verdicts: list[QualityMetricVerdict]) -> str:
    scored = [v for v in verdicts if v.verdict in _VERDICT_WEIGHTS]
    if not scored:
        return "indeterminado"
    total = sum(_VERDICT_WEIGHTS[v.verdict] for v in scored)
    if total < 0:
        return "alta"
    if total > 0:
        return "baixa"
    return "média"


class QualityEngine:
    """Classifica a qualidade de um ativo a partir de indicadores e bandas fixas."""

    def evaluate(
        self,
        ticker: str,
        asset_class: str,
        snapshot: FundamentalSnapshotResult | None,
    ) -> QualityResult:
        if asset_class not in APPLICABLE_CLASSES:
            return QualityResult(
                ticker=ticker,
                asset_class=asset_class,
                classification="indeterminado",
                confidence="baixa",
                reason=(
                    f"indicadores de qualidade para a classe '{asset_class}' "
                    "ainda não implementados"
                ),
            )

        if snapshot is None:
            return QualityResult(
                ticker=ticker,
                asset_class=asset_class,
                classification="indeterminado",
                confidence="baixa",
                reason="nenhum snapshot de fundamentos disponível",
            )

        verdicts: list[QualityMetricVerdict] = []
        for band in QUALITY_BANDS:
            value = getattr(snapshot, band.field, None)
            if value is None:
                verdicts.append(
                    QualityMetricVerdict(
                        field=band.field,
                        label=band.label,
                        value=None,
                        verdict="indeterminado",
                        reason=f"{band.label} indisponível para {ticker}",
                    )
                )
                continue
            verdicts.append(
                QualityMetricVerdict(
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

        return QualityResult(
            ticker=ticker,
            asset_class=asset_class,
            classification=_overall_classification(verdicts),
            metrics=verdicts,
            confidence=confidence,
        )
