"""Data contract de fundamentos (Sprint 13 / Fase 2).

Formato normalizado de fundamentos vindo de qualquer fonte externa,
independente do provider — mesmo papel de `PriceData` para preços.
Todo campo é opcional: nenhum dado entra em `fundamental_snapshots`
sem passar por este contrato, e a ausência de um campo aqui é o sinal
correto de "não disponível", nunca um erro.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class FundamentalData(BaseModel):
    """Fundamentos normalizados de um ativo numa data de referência."""

    ticker: str
    period_end: date
    source_name: str
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
