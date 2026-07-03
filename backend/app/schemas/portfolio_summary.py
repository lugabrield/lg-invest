"""Schemas de saída do Portfolio Engine (Volume 20, prompt 8).

Estruturas serializáveis que descrevem o estado da carteira. Consumidas
pela CLI, pela futura API e pela tela Streamlit — todas leem daqui, sem
recalcular nada (princípio: cálculo só na engine).
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class PositionResult(BaseModel):
    """Resultado calculado de uma posição."""

    ticker: str
    asset_class: str
    currency: str
    quantity: Decimal
    average_price: Decimal
    current_price: Decimal
    position_value: Decimal
    weight: Decimal  # fração 0..1
    return_pct: Decimal | None  # None quando average_price == 0


class AllocationSlice(BaseModel):
    """Uma fatia de alocação (por classe ou por moeda)."""

    label: str
    value: Decimal
    weight: Decimal  # fração 0..1


class PortfolioSummary(BaseModel):
    """Resumo consolidado da carteira (Portfolio Engine v1)."""

    total_value: Decimal
    total_cost: Decimal
    total_return_pct: Decimal | None
    is_multi_currency: bool

    positions: list[PositionResult]
    allocation_by_class: list[AllocationSlice]
    allocation_by_currency: list[AllocationSlice]

    largest_position_ticker: str | None
    concentration_hhi: Decimal
    effective_number_of_assets: Decimal | None

    unpriced_tickers: list[str]  # posições sem preço atual, excluídas dos totais

    model_config = {"from_attributes": True}
