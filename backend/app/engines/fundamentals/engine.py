"""Fundamentals Engine — cálculo puro de CAGR e tendência de margem.

Recebe uma lista de `FundamentalSnapshotResult` (já carregada pelo
serviço a partir do repositório) e devolve um `FundamentalsAnalysisResult`
imutável. Não acessa banco, yfinance nem Streamlit.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.engines.fundamentals.cagr import compute_cagr
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.fundamentals_analysis import FundamentalsAnalysisResult

_MIN_PERIODS_FOR_TREND = 2
_MARGIN_TREND_THRESHOLD = Decimal("0.01")  # 1 p.p. de variação mínima para não ser "estável"


def _series(snapshots: list[FundamentalSnapshotResult], field: str) -> list[tuple[date, Decimal]]:
    pairs = [(s.period_end, getattr(s, field)) for s in snapshots]
    pairs = [(d, v) for d, v in pairs if v is not None]
    pairs.sort(key=lambda item: item[0])
    return pairs


def _margin_trend(snapshots: list[FundamentalSnapshotResult]) -> tuple[str, str | None]:
    series = _series(snapshots, "net_margin")
    if len(series) < _MIN_PERIODS_FOR_TREND:
        return "indeterminado", "histórico insuficiente para avaliar tendência de margem"

    delta = series[-1][1] - series[0][1]
    if delta > _MARGIN_TREND_THRESHOLD:
        return "melhorando", None
    if delta < -_MARGIN_TREND_THRESHOLD:
        return "piorando", None
    return "estável", None


class FundamentalsEngine:
    """Deriva CAGR e tendências a partir de uma série de snapshots de um ativo."""

    def analyze(
        self, ticker: str, snapshots: list[FundamentalSnapshotResult]
    ) -> FundamentalsAnalysisResult:
        if not snapshots:
            return FundamentalsAnalysisResult(
                ticker=ticker,
                periods_used=0,
                confidence="baixa",
                reason="nenhum snapshot de fundamentos disponível",
            )

        ordered = sorted(snapshots, key=lambda s: s.period_end)

        revenue_cagr, revenue_reason = compute_cagr(_series(ordered, "revenue"))
        net_income_cagr, net_income_reason = compute_cagr(_series(ordered, "net_income"))
        ebitda_cagr, ebitda_reason = compute_cagr(_series(ordered, "ebitda"))
        fcf_cagr, fcf_reason = compute_cagr(_series(ordered, "free_cash_flow"))
        margin_trend, margin_trend_reason = _margin_trend(ordered)

        computed = (revenue_cagr, net_income_cagr, ebitda_cagr, fcf_cagr)
        available = sum(1 for c in computed if c is not None)
        if available == 0:
            confidence = "baixa"
        elif available < len(computed):
            confidence = "média"
        else:
            confidence = "alta"

        return FundamentalsAnalysisResult(
            ticker=ticker,
            periods_used=len(ordered),
            revenue_cagr=revenue_cagr,
            revenue_cagr_reason=revenue_reason,
            net_income_cagr=net_income_cagr,
            net_income_cagr_reason=net_income_reason,
            ebitda_cagr=ebitda_cagr,
            ebitda_cagr_reason=ebitda_reason,
            fcf_cagr=fcf_cagr,
            fcf_cagr_reason=fcf_reason,
            margin_trend=margin_trend,
            margin_trend_reason=margin_trend_reason,
            confidence=confidence,
        )
