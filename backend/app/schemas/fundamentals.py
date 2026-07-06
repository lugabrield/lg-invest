"""Schemas de fundamentos (Sprint 13 / Fase 2).

`FundamentalSnapshotResult` carrega TODOS os campos como opcionais e
expõe `coverage_pct`/`missing_fields` para que UI e engines saibam
exatamente quanto do indicador está disponível — nunca inferimos ou
inventamos um valor ausente (Volume 18 §8).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

# Campos financeiros considerados para cálculo de cobertura/confiança.
_RATIO_FIELDS = (
    "roe",
    "roa",
    "net_margin",
    "ebitda_margin",
    "revenue",
    "net_income",
    "ebitda",
    "ebit",
    "free_cash_flow",
    "net_debt",
    "debt_to_ebitda",
    "pe_ratio",
    "pb_ratio",
    "ev_ebitda",
    "dividend_yield",
    "payout_ratio",
    "eps",
    "revenue_per_share",
    "beta",
    "market_cap",
    "enterprise_value",
    "forward_pe",
    "operating_margin",
    "total_debt",
    "total_cash",
    "operating_cash_flow",
    "gross_profit",
    "shares_outstanding",
)


class FundamentalSnapshotResult(BaseModel):
    """Fundamentos de um ativo em um período, prontos para exibição/consumo."""

    ticker: str
    period_end: date
    source: str  # "yahoo" | "manual" | "unavailable"
    collected_at: datetime

    roe: Decimal | None = None
    roa: Decimal | None = None
    net_margin: Decimal | None = None
    ebitda_margin: Decimal | None = None
    revenue: Decimal | None = None
    net_income: Decimal | None = None
    ebitda: Decimal | None = None
    ebit: Decimal | None = None
    free_cash_flow: Decimal | None = None
    net_debt: Decimal | None = None
    debt_to_ebitda: Decimal | None = None
    pe_ratio: Decimal | None = None
    pb_ratio: Decimal | None = None
    ev_ebitda: Decimal | None = None
    dividend_yield: Decimal | None = None
    payout_ratio: Decimal | None = None
    eps: Decimal | None = None
    revenue_per_share: Decimal | None = None
    beta: Decimal | None = None

    # Sprint 21 — campos adicionais de fundamentos (Fundamentals Foundation).
    market_cap: Decimal | None = None
    enterprise_value: Decimal | None = None
    forward_pe: Decimal | None = None
    operating_margin: Decimal | None = None
    total_debt: Decimal | None = None
    total_cash: Decimal | None = None
    operating_cash_flow: Decimal | None = None
    gross_profit: Decimal | None = None
    shares_outstanding: Decimal | None = None

    model_config = {"from_attributes": True}

    @property
    def missing_fields(self) -> list[str]:
        return [f for f in _RATIO_FIELDS if getattr(self, f) is None]

    @property
    def coverage_pct(self) -> Decimal:
        """Fração (0..1) dos campos financeiros disponíveis neste snapshot."""
        available = len(_RATIO_FIELDS) - len(self.missing_fields)
        return Decimal(available) / Decimal(len(_RATIO_FIELDS))


class FundamentalsCollectionResult(BaseModel):
    """Resultado da coleta de fundamentos de um único ativo."""

    ticker: str
    collected: bool
    period_end: date | None = None
    reason: str | None = None  # ex.: "classe não aplicável", "ativo manual", "sem dado do provider"
    error: str | None = None


class BatchFundamentalsResult(BaseModel):
    """Resultado agregado da coleta de fundamentos de um lote de ativos."""

    results: list[FundamentalsCollectionResult] = []

    @property
    def total_collected(self) -> int:
        return sum(1 for r in self.results if r.collected)

    @property
    def total_skipped(self) -> int:
        return sum(1 for r in self.results if not r.collected and r.error is None)

    @property
    def failed(self) -> list[str]:
        return [r.ticker for r in self.results if r.error]
