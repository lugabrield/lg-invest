"""Schemas do Data Quality Layer (Sprint 21).

Superfície única e explícita de "o quão confiável é o que a LG INVEST
está mostrando" para um ativo e para a carteira como um todo. Não
recalcula nada: compõe sinais que os outros serviços já produzem (fonte
do preço, presença de fundamentos, classificação de valuation,
confiança do LG Conviction Score). Ver docs/DATA_QUALITY.md.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

# Status possíveis por dimensão. Strings em snake_case (não em português
# com acento) porque viram chave de dicionário/CSS var em vários lugares
# do frontend (`components/badges.py`).
PRICE_STATUSES = ("automatico", "manual", "estimado", "ausente")
FUNDAMENTALS_STATUSES = ("completo", "parcial", "ausente", "nao_aplicavel")
VALUATION_STATUSES = ("real", "proxy", "nao_aplicavel", "ausente")
SCORE_CONFIDENCE_STATUSES = ("alta", "média", "baixa", "indisponivel")


class AssetDataQuality(BaseModel):
    """Classificação de qualidade de dado de um único ativo."""

    ticker: str
    asset_class: str

    price_status: str  # ver PRICE_STATUSES
    fundamentals_status: str  # ver FUNDAMENTALS_STATUSES
    fundamentals_fields_available: int = 0
    fundamentals_fields_total: int = 0
    valuation_status: str  # ver VALUATION_STATUSES
    score_confidence: str  # ver SCORE_CONFIDENCE_STATUSES

    issues: list[str] = []
    """Lista curta de avisos legíveis, ex.: 'sem fundamentos coletados', 'preço estimado'."""

    @property
    def is_fully_reliable(self) -> bool:
        """Verdadeiro só quando preço é automático, fundamentos completos e valuation real."""
        return (
            self.price_status == "automatico"
            and self.fundamentals_status == "completo"
            and self.valuation_status == "real"
        )


class PortfolioDataQualitySummary(BaseModel):
    """Resumo de qualidade de dado agregado por carteira (ponderado por peso quando aplicável)."""

    total_assets: int = 0
    pct_price_automatic: Decimal = Decimal("0")
    pct_price_manual: Decimal = Decimal("0")
    pct_price_estimated: Decimal = Decimal("0")
    pct_fundamentals_available: Decimal = Decimal("0")  # completo ou parcial
    pct_valuation_available: Decimal = Decimal("0")  # real ou proxy

    assets_insufficient_data: list[str] = []
    """Tickers com fundamentos ausentes E valuation ausente (não é 'não aplicável')."""
    assets_manual: list[str] = []
    assets_price_estimated: list[str] = []
    assets_unsupported_by_provider: list[str] = []
    """Tickers cuja classe não é suportada pelo provider de fundamentos (ex.: cripto)."""

    per_asset: list[AssetDataQuality] = []
