"""Schema da lista de ativos cadastrados (v1.1, Fase 6).

Espelha `_asset_row()` de `frontend/streamlit_app/pages_impl/ativos.py`,
mas sem formatação de apresentação (isso fica no frontend) — devolve os
valores crus (Decimal como string, datetime como ISO) para o Next.js
formatar do jeito que quiser.
"""

from __future__ import annotations

from pydantic import BaseModel

PRICE_STATUSES = ("automatic", "manual", "missing")


class AssetRowView(BaseModel):
    ticker: str
    name: str
    asset_class: str
    country: str
    currency: str
    sector: str | None = None
    price: str | None = None
    price_status: str  # ver PRICE_STATUSES
    is_manual: bool
    updated_at: str | None = None  # ISO 8601
