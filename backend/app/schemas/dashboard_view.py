"""Schemas do view-model do Dashboard (Sprint 11).

Estruturas serializáveis que descrevem a carteira já pronta para
exibição: conversão cambial USD->BRL e fallback de preço aplicados.
Não são saída de nenhuma engine — são montadas por
`dashboard_view_service.build_dashboard_view` a partir do
`PortfolioSummary` (Portfolio Engine, inalterado). Vivem em `schemas/`
pelo mesmo motivo dos demais: serialização e consumo por múltiplas
telas sem recalcular nada.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ConvertedPosition(BaseModel):
    """Uma posição pronta para exibição: valores nominais + convertidos."""

    ticker: str
    asset_class: str
    currency: str
    quantity: Decimal
    average_price: Decimal
    current_price: Decimal
    position_value: Decimal  # valor na moeda original
    position_value_brl: Decimal  # valor convertido para BRL
    weight: Decimal  # peso sobre o total já convertido
    return_pct: Decimal | None
    is_price_estimated: bool  # True quando não havia cotação e usamos average_price
    group_label: str  # Ações BR, FIIs, Ações EUA, ETFs, REITs, Cripto, Renda Fixa

    price_source: str  # "yahoo" | "manual" | "estimated"
    price_updated_at: datetime | None  # None quando não há nenhum Price salvo

    model_config = {"from_attributes": True}


class CurrencyExposure(BaseModel):
    """Exposição por moeda, já convertida para BRL."""

    currency: str
    value_brl: Decimal
    weight: Decimal  # fração 0..1 sobre o total convertido

    model_config = {"from_attributes": True}


class DashboardView(BaseModel):
    """View-model consolidado consumido pelas telas Dashboard, Carteira e Aporte."""

    exchange_rate: Decimal
    total_brl: Decimal  # soma nominal das posições em BRL
    total_usd: Decimal  # soma nominal das posições em USD
    total_converted_brl: Decimal  # patrimônio total convertido para BRL
    total_cost_brl: Decimal  # custo total convertido para BRL (para rentabilidade agregada)
    total_return_pct: Decimal | None
    is_multi_currency: bool

    currency_exposure: list[CurrencyExposure]
    positions: list[ConvertedPosition]

    largest_position_ticker: str | None
    concentration_hhi: Decimal
    effective_number_of_assets: Decimal | None

    estimated_price_tickers: list[str] = []
    manual_price_tickers: list[str] = []
    unpriced_tickers: list[str] = []

    model_config = {"from_attributes": True}
