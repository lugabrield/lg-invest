"""Schemas das ações de escrita da tela Ativos (v1.1, Fase 6).

Cobre os 5 formulários de `pages_impl/ativos.py` que gravam algo:
marcar/desmarcar ativo como manual, cadastrar preço manual, atualizar
preço automático (Yahoo Finance), coletar fundamentos (um ativo ou
todos) e importar fundamentos via CSV/Excel. Nenhuma regra nova: os
services por trás (`FundamentalsImportService`, `FundamentalsService`,
`MarketDataService`) continuam exatamente os mesmos usados pelo
Streamlit.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from backend.app.schemas.fundamentals import BatchFundamentalsResult, FundamentalsCollectionResult
from backend.app.schemas.market_data import UpdateResult


class ManualFlagRequest(BaseModel):
    is_manual: bool


class ManualFlagResponse(BaseModel):
    ticker: str
    is_manual: bool


class ManualPriceRequest(BaseModel):
    price: Decimal


class ManualPriceResponse(BaseModel):
    ticker: str
    price: str
    source: str = "manual"


class RefreshPriceResponse(BaseModel):
    result: UpdateResult


class CollectFundamentalsResponse(BaseModel):
    result: FundamentalsCollectionResult


class CollectFundamentalsBatchResponse(BaseModel):
    result: BatchFundamentalsResult


class FundamentalsImportRowOutcomeView(BaseModel):
    line: int
    ticker: str
    period_end: str | None
    status: str
    fields_applied: list[str]
    reported_source: str | None
    message: str | None


class FundamentalsImportRowErrorView(BaseModel):
    line: int
    field: str | None
    message: str


class FundamentalsImportResultView(BaseModel):
    total_rows: int
    imported: int
    conflicts_pending: int
    outcomes: list[FundamentalsImportRowOutcomeView]
    errors: list[FundamentalsImportRowErrorView]
    tickers_recomputed: list[str]
    valuation_recalculated: int
    traps_recalculated: int
    scores_recalculated: int
