"""Análise de Renda Imobiliária — orquestração pura (Sprint 26, Fase 4).

Combina P/VP, Dividend Yield e a estabilidade histórica do DY numa
`IncomeRealEstateAnalysisResult`. Nunca usa DCF nem P/L — nunca gera
recomendação de compra/venda. Escopo: `fii` e `reit`.

REITs (EUA) idealmente seriam analisados via FFO/AFFO (Funds/Adjusted
Funds From Operations), não via lucro contábil — mas este projeto ainda
não coleta esses campos (não expostos com confiança pelo yfinance sem
mapeamento dedicado). Em vez de aproximar FFO a partir de um número que
não é FFO (o que violaria "nunca inventar dado"), REITs usam a mesma
leitura de P/VP + DY que os FIIs, com aviso explícito da limitação e
confiança nunca "alta" — é a estratégia "melhor esforço + confiança
baixa" já aprovada para esta sprint.
"""

from __future__ import annotations

from backend.app.engines.income_real_estate.stability import dy_stability
from backend.app.engines.income_real_estate.thresholds import (
    DY_ATTRACTIVE_THRESHOLD,
    DY_LOW_THRESHOLD,
    PVP_CHEAP_THRESHOLD,
    PVP_EXPENSIVE_THRESHOLD,
)
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.income_real_estate import (
    DY_STABILITY_INDETERMINATE,
    DY_STABILITY_UNSTABLE,
    INSUFFICIENT_DATA_MESSAGE,
    STATUS_ATTRACTIVE,
    STATUS_NEUTRAL,
    STATUS_UNATTRACTIVE,
    IncomeRealEstateAnalysisResult,
)

_APPLICABLE_ASSET_CLASSES = ("fii", "reit")


class IncomeRealEstateEngine:
    """Analisa FIIs/REITs via P/VP + DY + estabilidade — nunca DCF/P-L."""

    def evaluate(
        self,
        ticker: str,
        asset_class: str,
        latest_snapshot: FundamentalSnapshotResult | None,
        history: list[FundamentalSnapshotResult],
    ) -> IncomeRealEstateAnalysisResult:
        if asset_class not in _APPLICABLE_ASSET_CLASSES:
            return IncomeRealEstateAnalysisResult(
                ticker=ticker,
                asset_class=asset_class,
                reason=(
                    f"classe '{asset_class}' fora do escopo desta análise (cobre apenas "
                    "FIIs e REITs — Sprint 26, Fase 4)"
                ),
            )

        if latest_snapshot is None:
            return IncomeRealEstateAnalysisResult(
                ticker=ticker, asset_class=asset_class, reason=INSUFFICIENT_DATA_MESSAGE
            )

        pvp = latest_snapshot.pb_ratio
        dy = latest_snapshot.dividend_yield
        dy_series = [s.dividend_yield for s in history if s.dividend_yield is not None]

        warnings: list[str] = []
        methodology: list[str] = []
        score = 0

        if pvp is not None and pvp > 0:
            methodology.append("pvp")
            if pvp <= PVP_CHEAP_THRESHOLD:
                score += 1
            elif pvp >= PVP_EXPENSIVE_THRESHOLD:
                score -= 1

        if dy is not None and dy > 0:
            methodology.append("dividend_yield")
            if dy >= DY_ATTRACTIVE_THRESHOLD:
                score += 1
            elif dy < DY_LOW_THRESHOLD:
                score -= 1

        stability, dy_average, stability_reason = dy_stability(dy_series)
        if stability == DY_STABILITY_UNSTABLE:
            score -= 1
            warnings.append(
                "Dividend Yield instável ao longo do histórico do próprio ativo — o número "
                "do período mais recente pode não representar a renda recorrente esperada."
            )
        elif stability != DY_STABILITY_INDETERMINATE:
            methodology.append("dy_stability")
        elif stability_reason:
            warnings.append(f"Estabilidade do DY indeterminada: {stability_reason}.")

        if asset_class == "reit":
            warnings.append(
                "REITs idealmente usam FFO/AFFO (Funds From Operations) em vez de P/VP "
                "contábil — esta fonte de dados não coleta FFO/AFFO ainda, então a análise "
                "usa P/VP e DY como aproximação disponível, com confiança limitada."
            )

        if pvp is None and dy is None:
            return IncomeRealEstateAnalysisResult(
                ticker=ticker,
                asset_class=asset_class,
                dy_stability=stability,
                warnings=warnings,
                reason=INSUFFICIENT_DATA_MESSAGE,
                confidence="baixa",
            )

        if score >= 2:
            status = STATUS_ATTRACTIVE
        elif score <= -1:
            status = STATUS_UNATTRACTIVE
        else:
            status = STATUS_NEUTRAL

        core_methods = {m for m in methodology if m in ("pvp", "dividend_yield")}
        if len(core_methods) == 2 and stability != DY_STABILITY_INDETERMINATE:
            confidence = "média" if asset_class == "reit" else "alta"
        elif core_methods:
            confidence = "média" if asset_class != "reit" else "baixa"
        else:
            confidence = "baixa"

        return IncomeRealEstateAnalysisResult(
            ticker=ticker,
            asset_class=asset_class,
            status=status,
            pvp=pvp,
            dividend_yield=dy,
            dy_own_history_average=dy_average,
            dy_stability=stability,
            confidence=confidence,
            warnings=warnings,
            methodology=methodology,
        )
