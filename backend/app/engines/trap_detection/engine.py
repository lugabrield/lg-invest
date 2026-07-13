"""Trap Detection Engine — orquestração pura (Sprint 26, Fases 3-4).

Roda os detectores de armadilha aplicáveis à classe do ativo sobre o
snapshot mais recente de fundamentos, a análise histórica (CAGR), o
resultado do Valuation Engine 2.0 (ações) ou da Análise de Renda
Imobiliária (FIIs/REITs), e agrega tudo numa `TrapDetectionResult`. Nunca
gera recomendação de compra/venda — só flags, cada um com severidade,
explicação e uma penalidade de confiança que quem consome este resultado
deve aplicar (nunca os detectores decidindo um score final sozinhos).

Escopo: ações (`asset_class == "stock"`) usam os 5 detectores da Fase 3
(Low P/E, Low P/B, Growth Overpriced, Leverage, Data Quality). FIIs/REITs
(`asset_class in ("fii", "reit")`) usam os 2 detectores da Fase 4 (High
DY Trap, FII Yield Trap) — nunca os detectores de ações, que dependem de
conceitos (P/L, DCF) que não se aplicam a fundos/REITs.
"""

from __future__ import annotations

from decimal import Decimal

from backend.app.engines.trap_detection.detectors import (
    detect_data_quality_trap,
    detect_fii_yield_trap,
    detect_growth_overpriced_trap,
    detect_high_dy_trap,
    detect_leverage_trap,
    detect_low_pb_trap,
    detect_low_pe_trap,
)
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.fundamentals_analysis import FundamentalsAnalysisResult
from backend.app.schemas.income_real_estate import IncomeRealEstateAnalysisResult
from backend.app.schemas.trap_detection import TrapDetectionResult
from backend.app.schemas.valuation_v2 import ValuationV2Result

_APPLICABLE_ASSET_CLASSES = ("stock", "fii", "reit")
_STOCK_ASSET_CLASSES = ("stock",)
_INCOME_REAL_ESTATE_ASSET_CLASSES = ("fii", "reit")
_MAX_CONFIDENCE_PENALTY = Decimal("1.0")


def _historical_growth(
    analysis: FundamentalsAnalysisResult | None,
) -> tuple[Decimal | None, str | None]:
    """Mesma prioridade usada pelo Valuation Engine 2.0 (FCF > lucro >
    receita) — duplicado deliberadamente para o Trap Detection Engine não
    depender do motor de valuation além do resultado já pronto que recebe."""
    if analysis is None:
        return None, None
    if analysis.fcf_cagr is not None:
        return analysis.fcf_cagr, "FCF"
    if analysis.net_income_cagr is not None:
        return analysis.net_income_cagr, "lucro líquido"
    if analysis.revenue_cagr is not None:
        return analysis.revenue_cagr, "receita"
    return None, None


class TrapDetectionEngine:
    """Varre um ativo em busca de padrões clássicos de armadilha de valuation."""

    def evaluate(
        self,
        ticker: str,
        asset_class: str,
        latest_snapshot: FundamentalSnapshotResult | None,
        fundamentals_analysis: FundamentalsAnalysisResult | None,
        valuation: ValuationV2Result | None,
        income_real_estate: IncomeRealEstateAnalysisResult | None = None,
    ) -> TrapDetectionResult:
        if asset_class not in _APPLICABLE_ASSET_CLASSES:
            return TrapDetectionResult(
                ticker=ticker,
                asset_class=asset_class,
                reason=(
                    f"classe '{asset_class}' fora do escopo do Trap Detection Engine "
                    "(cobre ações, FIIs e REITs — Sprint 26, Fases 3-4)"
                ),
            )

        if latest_snapshot is None:
            return TrapDetectionResult(
                ticker=ticker,
                asset_class=asset_class,
                reason="nenhum snapshot de fundamentos disponível para varrer armadilhas",
            )

        if asset_class in _INCOME_REAL_ESTATE_ASSET_CLASSES:
            dy_own_history_average = (
                income_real_estate.dy_own_history_average if income_real_estate else None
            )
            flags = [
                detect_high_dy_trap(dividend_yield=latest_snapshot.dividend_yield),
                detect_fii_yield_trap(
                    dividend_yield=latest_snapshot.dividend_yield,
                    dy_own_history_average=dy_own_history_average,
                ),
            ]
        else:
            historical_growth, growth_source = _historical_growth(fundamentals_analysis)
            periods_used = fundamentals_analysis.periods_used if fundamentals_analysis else 0
            implied_growth_rate = valuation.implied_growth_rate if valuation is not None else None

            flags = [
                detect_low_pe_trap(
                    pe_ratio=latest_snapshot.pe_ratio,
                    net_income_cagr=(
                        fundamentals_analysis.net_income_cagr if fundamentals_analysis else None
                    ),
                    margin_trend=(
                        fundamentals_analysis.margin_trend if fundamentals_analysis else None
                    ),
                ),
                detect_low_pb_trap(pb_ratio=latest_snapshot.pb_ratio, roe=latest_snapshot.roe),
                detect_growth_overpriced_trap(
                    implied_growth_rate=implied_growth_rate,
                    historical_growth_rate=historical_growth,
                    growth_source=growth_source,
                ),
                detect_leverage_trap(
                    debt_to_ebitda=latest_snapshot.debt_to_ebitda,
                    interest_coverage=latest_snapshot.interest_coverage,
                ),
                detect_data_quality_trap(
                    coverage_pct=latest_snapshot.coverage_pct, periods_used=periods_used
                ),
            ]
        active_flags = [flag for flag in flags if flag is not None]

        total_penalty = sum((flag.confidence_penalty for flag in active_flags), Decimal("0"))
        total_penalty = min(total_penalty, _MAX_CONFIDENCE_PENALTY)

        return TrapDetectionResult(
            ticker=ticker,
            asset_class=asset_class,
            flags=active_flags,
            confidence_penalty=total_penalty,
        )
