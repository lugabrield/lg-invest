"""Schema de saída do Fundamentals Engine (Sprint 14 / Fase 2)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

# "alta": todos os CAGRs calculáveis; "média": parte deles; "baixa": nenhum
# (ou nenhum snapshot). Nunca inferimos um valor a partir da confiança —
# é só um resumo para a UI/engines futuras (Volume 18 §8).
CONFIDENCE_LEVELS = ("alta", "média", "baixa")
MARGIN_TRENDS = ("melhorando", "estável", "piorando", "indeterminado")


class FundamentalsAnalysisResult(BaseModel):
    """Indicadores derivados de uma série de snapshots de um ativo."""

    ticker: str
    periods_used: int = 0

    revenue_cagr: Decimal | None = None
    revenue_cagr_reason: str | None = None
    net_income_cagr: Decimal | None = None
    net_income_cagr_reason: str | None = None
    ebitda_cagr: Decimal | None = None
    ebitda_cagr_reason: str | None = None
    fcf_cagr: Decimal | None = None
    fcf_cagr_reason: str | None = None

    margin_trend: str = "indeterminado"
    margin_trend_reason: str | None = None

    confidence: str = "baixa"
    reason: str | None = None  # motivo geral, ex.: "nenhum snapshot disponível"
