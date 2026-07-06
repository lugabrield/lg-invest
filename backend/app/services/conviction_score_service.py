"""Serviço do LG Conviction Score v2 (Sprint 17 / Fase 2; Sprint 21).

Fronteira banco↔engine: monta o `ScoreInput` (preço) e busca os
resultados dos engines de fundamentos já existentes (Quality/Growth/
Risk/Valuation/Capital Reinvestment), então chama
`calculate_conviction_score_v2` (engine pura). Qualquer resultado
ausente vira fallback de pilar individual dentro do próprio engine —
nada é decidido aqui.

Sprint 21: o pilar de Capital Reinvestment passou a usar
`CapitalReinvestmentService` (engine dedicado) em vez de receber o
snapshot bruto e calcular a fórmula aqui — mesmo padrão dos outros
quatro pilares.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.engines.ids_methodology.engine import calculate_conviction_score_v2
from backend.app.engines.lg_score.inputs import ScoreInput
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.price_repository import PriceRepository
from backend.app.schemas.ids_methodology import ConvictionScoreResult
from backend.app.services.capital_reinvestment_service import CapitalReinvestmentService
from backend.app.services.growth_service import GrowthService
from backend.app.services.quality_service import QualityService
from backend.app.services.risk_service import RiskService
from backend.app.services.valuation_service import ValuationService


class ConvictionScoreService:
    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.prices = PriceRepository(db)
        self.quality_service = QualityService(db)
        self.growth_service = GrowthService(db)
        self.risk_service = RiskService(db)
        self.valuation_service = ValuationService(db)
        self.reinvestment_service = CapitalReinvestmentService(db)

    def score_ticker(
        self, ticker: str, current_weight=None, target_weight=None
    ) -> ConvictionScoreResult | None:
        asset = self.assets.get_by_ticker(ticker)
        if asset is None:
            return None

        price_history = [p.close for p in self.prices.list_by_asset(asset.id)]
        data = ScoreInput(
            ticker=asset.ticker,
            asset_class=asset.asset_class,
            price_history=price_history,
            current_weight=current_weight,
            target_weight=target_weight,
        )

        return calculate_conviction_score_v2(
            data,
            quality_result=self.quality_service.evaluate_ticker(ticker),
            growth_result=self.growth_service.evaluate_ticker(ticker),
            risk_result=self.risk_service.evaluate_ticker(ticker),
            valuation_result=self.valuation_service.evaluate_ticker(ticker),
            reinvestment_result=self.reinvestment_service.evaluate_ticker(ticker),
        )
