"""Serviço do Data Quality Layer (Sprint 21).

Fronteira banco↔engine: para cada posição da carteira, resolve os
sinais brutos (fonte do preço, contagem de campos de fundamentos
preenchidos, classificação de valuation, confiança do LG Conviction
Score) e chama o `engines/data_quality/engine.py` (puro) para
classificar e agregar. Reaproveita os serviços já existentes
(`ValuationService`, `ConvictionScoreService`, `FundamentalsRepository`)
em vez de reimplementar a lógica deles — este serviço só compõe.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.engines.data_quality.engine import (
    build_asset_data_quality,
    build_portfolio_summary,
)
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.infrastructure.repositories.price_repository import PriceRepository
from backend.app.schemas.data_quality import AssetDataQuality, PortfolioDataQualitySummary
from backend.app.services.conviction_score_service import ConvictionScoreService
from backend.app.services.fundamentals_service import NOT_APPLICABLE_CLASSES as FUNDAMENTALS_NA
from backend.app.services.portfolio_service import PortfolioService
from backend.app.services.valuation_service import ValuationService

_FUNDAMENTALS_FIELDS = (
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

# Mesma lista do Valuation Engine (thresholds.py) — duplicada deliberadamente,
# mesma convenção usada pelos outros serviços que consomem essa fronteira.
_VALUATION_NOT_APPLICABLE_CLASSES = ("crypto", "cash", "bond", "etf")

# FIIs são fundos, não empresas operacionais: ROE/P-L/margem (parte dos
# 28 campos de `_FUNDAMENTALS_FIELDS`) raramente são métricas
# significativas para eles, mesmo quando o Yahoo Finance retorna algum
# valor. Para não inflar artificialmente a cobertura/confiança de FII
# com campos que não deveriam pesar, a cobertura de fundamentos de FII
# é calculada só sobre este subconjunto — o que de fato é usado para
# avaliar FIIs (Valuation Engine, `engines/valuation/thresholds.py`) —
# em vez dos 28 campos completos (Sprint 22).
_FII_PRIORITY_FIELDS = ("pb_ratio", "dividend_yield")


class DataQualityService:
    def __init__(self, db: Session):
        self.db = db
        self.prices = PriceRepository(db)
        self.fundamentals = FundamentalsRepository(db)
        self.portfolio_service = PortfolioService(db)
        self.valuation_service = ValuationService(db)
        self.conviction_service = ConvictionScoreService(db)

    def evaluate_ticker(
        self, ticker: str, asset_id: int, asset_class: str, *, is_manual: bool = False
    ) -> AssetDataQuality:
        """Classifica a qualidade de dado de um único ativo já cadastrado."""
        latest_price = self.prices.get_latest(asset_id)
        is_price_estimated = latest_price is None
        price_source = None if latest_price is None else latest_price.source

        latest_snapshot = self.fundamentals.get_latest(asset_id)
        fundamentals_fields = _FII_PRIORITY_FIELDS if asset_class == "fii" else _FUNDAMENTALS_FIELDS
        fields_available = 0
        if latest_snapshot is not None:
            fields_available = sum(
                1
                for field in fundamentals_fields
                if getattr(latest_snapshot, field, None) is not None
            )
        fundamentals_applicable = asset_class not in FUNDAMENTALS_NA

        valuation_result = self.valuation_service.evaluate_ticker(ticker)
        valuation_applicable = asset_class not in _VALUATION_NOT_APPLICABLE_CLASSES

        conviction = self.conviction_service.score_ticker(ticker)
        score_confidence_label = conviction.confidence_label if conviction is not None else None

        return build_asset_data_quality(
            ticker=ticker,
            asset_class=asset_class,
            price_source=price_source,
            is_price_estimated=is_price_estimated,
            fundamentals_fields_available=fields_available,
            fundamentals_fields_total=len(fundamentals_fields),
            fundamentals_applicable=fundamentals_applicable,
            valuation_classification=(
                valuation_result.classification if valuation_result is not None else None
            ),
            valuation_applicable=valuation_applicable,
            score_confidence_label=score_confidence_label,
            is_manual=is_manual,
        )

    def evaluate_portfolio(self, portfolio_id: int) -> PortfolioDataQualitySummary:
        """Classifica a qualidade de dado de todas as posições de uma carteira."""
        summary = self.portfolio_service.get_summary(portfolio_id)
        assets: list[AssetDataQuality] = []
        weights: dict[str, Decimal] = {}
        seen_tickers: set[str] = set()
        for pos in summary.positions:
            asset = self.portfolio_service.assets.get_by_ticker(pos.ticker)
            if asset is None:
                continue
            assets.append(
                self.evaluate_ticker(
                    pos.ticker, asset.id, pos.asset_class, is_manual=asset.is_manual
                )
            )
            weights[pos.ticker] = pos.weight
            seen_tickers.add(pos.ticker)

        # `PortfolioSummary.positions` só inclui posições com preço
        # resolvido (Portfolio Engine exclui o resto em
        # `unpriced_tickers`) — um ativo manual (ex.: Tesouro Direto)
        # ainda sem nenhum preço cadastrado cairia nesse grupo e
        # desapareceria da avaliação de qualidade de dado, voltando a
        # parecer "dado ausente" por omissão. Avalia também esses
        # tickers, com peso 0 (Sprint 22 — mesmo bug relatado para o
        # Dashboard, fechado aqui na camada de Data Quality).
        for ticker in summary.unpriced_tickers:
            if ticker in seen_tickers:
                continue
            asset = self.portfolio_service.assets.get_by_ticker(ticker)
            if asset is None:
                continue
            assets.append(
                self.evaluate_ticker(ticker, asset.id, asset.asset_class, is_manual=asset.is_manual)
            )
            weights[ticker] = Decimal("0")

        return build_portfolio_summary(assets, weights)
