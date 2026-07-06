"""Risk Engine v1 — classificação de risco por indicadores estáticos (pura).

Recebe o snapshot de fundamentos mais recente de um ativo (já
carregado pelo serviço) e devolve um `RiskResult`. Não acessa banco,
yfinance nem Streamlit. Ausência de indicador, classe fora do escopo ou
nenhum snapshot disponível nunca viram erro — viram veredito
"indeterminado" com razão explícita (Volume 18 §8).

Sprint 21: cripto passou a ter uma regra de POLÍTICA (não de dado) —
classificação "alto" fixa, com razão explícita de que é uma decisão de
metodologia (volatilidade estrutural, ausência de fundamentos de
empresa, tese predominantemente macro), não uma leitura de indicador
ausente/indeterminado. Isso é diferente de "não temos dado": aqui a
plataforma está afirmando algo sobre a classe, documentado em
docs/QUALITY_GROWTH_RISK_ENGINES.md.
"""

from __future__ import annotations

from backend.app.engines.risk.thresholds import NOT_APPLICABLE_CLASSES, bands_for_asset_class
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.risk import RiskMetricVerdict, RiskResult

_VERDICT_WEIGHTS = {"baixo": -1, "médio": 0, "alto": 1}

# Classes com risco definido por POLÍTICA da metodologia, não por
# indicador de balanço/mercado — sempre "alto", sem depender de
# fundamentos coletados (cripto não tem ROE/dívida/beta comparável a
# uma empresa). Ver docs/QUALITY_GROWTH_RISK_ENGINES.md.
_POLICY_HIGH_RISK_CLASSES = ("crypto",)


def _overall_classification(verdicts: list[RiskMetricVerdict]) -> str:
    scored = [v for v in verdicts if v.verdict in _VERDICT_WEIGHTS]
    if not scored:
        return "indeterminado"
    total = sum(_VERDICT_WEIGHTS[v.verdict] for v in scored)
    if total < 0:
        return "baixo"
    if total > 0:
        return "alto"
    return "médio"


class RiskEngine:
    """Classifica o risco de balanço/mercado de um ativo a partir de bandas fixas."""

    def evaluate(
        self,
        ticker: str,
        asset_class: str,
        snapshot: FundamentalSnapshotResult | None,
    ) -> RiskResult:
        if asset_class in _POLICY_HIGH_RISK_CLASSES:
            return RiskResult(
                ticker=ticker,
                asset_class=asset_class,
                classification="alto",
                confidence="alta",
                reason=(
                    "risco classificado como 'alto' por política da metodologia, não por "
                    "indicador de balanço: cripto não tem fundamentos de empresa "
                    "(ROE/dívida/beta comparáveis), tem volatilidade estruturalmente alta "
                    "e a tese de investimento é predominantemente macro — o LG Conviction "
                    "Score usa limite de exposição e confiança de dados no lugar de risco "
                    "de balanço para esta classe (ver profile.py)."
                ),
            )

        if asset_class in NOT_APPLICABLE_CLASSES:
            return RiskResult(
                ticker=ticker,
                asset_class=asset_class,
                classification="indeterminado",
                confidence="baixa",
                reason=(
                    f"indicadores de risco para a classe '{asset_class}' " "ainda não implementados"
                ),
            )

        bands = bands_for_asset_class(asset_class)
        if not bands:
            return RiskResult(
                ticker=ticker,
                asset_class=asset_class,
                classification="indeterminado",
                confidence="baixa",
                reason=f"nenhuma banda de risco definida para a classe '{asset_class}'",
            )

        if snapshot is None:
            return RiskResult(
                ticker=ticker,
                asset_class=asset_class,
                classification="indeterminado",
                confidence="baixa",
                reason="nenhum snapshot de fundamentos disponível",
            )

        verdicts: list[RiskMetricVerdict] = []
        for band in bands:
            value = getattr(snapshot, band.field, None)
            if value is None:
                verdicts.append(
                    RiskMetricVerdict(
                        field=band.field,
                        label=band.label,
                        value=None,
                        verdict="indeterminado",
                        reason=f"{band.label} indisponível para {ticker}",
                    )
                )
                continue
            verdicts.append(
                RiskMetricVerdict(
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

        return RiskResult(
            ticker=ticker,
            asset_class=asset_class,
            classification=_overall_classification(verdicts),
            metrics=verdicts,
            confidence=confidence,
        )
