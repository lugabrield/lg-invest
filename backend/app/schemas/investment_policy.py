"""Schema de InvestmentPolicy (Sprint 24, Fase 3)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class InvestmentPolicyView(BaseModel):
    """Espelho de leitura de `InvestmentPolicy` — usado pela UI e por
    engines que consultam os limites/parâmetros da política (nunca
    hardcoded dentro de uma engine)."""

    portfolio_id: int
    investor_profile: str
    horizon_years: int
    base_currency: str
    risk_tolerance: str

    max_asset_weight: Decimal
    max_crypto_weight: Decimal
    target_international_min: Decimal
    target_international_max: Decimal
    target_fii_max: Decimal

    target_brazil_equity: Decimal
    target_us_equity: Decimal
    target_etf: Decimal
    target_reit: Decimal
    target_fixed_income: Decimal

    rebalance_threshold: Decimal
    monthly_contribution_default: Decimal

    notes: str | None = None


class InvestmentPolicyUpdate(BaseModel):
    """Payload de atualização — todos os campos opcionais; só os
    enviados são alterados (permite editar um campo de cada vez na
    tela de Configurações sem reenviar a política inteira)."""

    investor_profile: str | None = None
    horizon_years: int | None = None
    base_currency: str | None = None
    risk_tolerance: str | None = None

    max_asset_weight: Decimal | None = None
    max_crypto_weight: Decimal | None = None
    target_international_min: Decimal | None = None
    target_international_max: Decimal | None = None
    target_fii_max: Decimal | None = None

    target_brazil_equity: Decimal | None = None
    target_us_equity: Decimal | None = None
    target_etf: Decimal | None = None
    target_reit: Decimal | None = None
    target_fixed_income: Decimal | None = None

    rebalance_threshold: Decimal | None = None
    monthly_contribution_default: Decimal | None = None

    notes: str | None = None
