"""Serviço do LG Conviction Score v2 (Sprint 17 / Fase 2).

Fronteira banco↔engine: monta o `ScoreInput` (preço) e busca os
resultados dos engines de fundamentos já existentes (Quality/Growth/
Risk/Valuation, Sprints 15-16) e o snapshot mais recente (para o pilar
de Capital Reinvestment), então chama `calculate_conviction_score_v2`
(engine pura). Qualquer resultado ausente vira fallback de pilar
individual dentro do próprio engine — nada é decidido aqui.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.engines.ids_methodology.engine import calculate_conviction_score_v2
from backend.app.engines.lg_score.inputs import ScoreInput
from backend.app.infrastructure.database.models.fundamental_snapshot import FundamentalSnapshot
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.infrastructure.repositories.price_repository import PriceRepository
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.ids_methodology import ConvictionScoreResult
from backend.app.services.growth_service import GrowthService
from backend.app.services.quality_service import QualityService
from backend.app.services.risk_service import RiskService
from backend.app.services.valuation_service import ValuationService

# Mesmos campos de backend/app/services/fundamentals_service.py::_SNAPSHOT_FIELDS
# — duplicado deliberadamente (mesma convenção usada nos outros serviços
# que consomem snapshots de fundamentos).
_SNAPSHOT_FIELDS = (
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
)


def _to_result(ticker: str, snapshot: FundamentalSnapshot) -> FundamentalSnapshotResult:
    return FundamentalSnapshotResult(
        ticker=ticker,
        period_end=snapshot.period_end,
        source=snapshot.source,
        collected_at=snapshot.updated_at,
        **{field: getattr(snapshot, field) for field in _SNAPSHOT_FIELDS},
    )


class ConvictionScoreService:
    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.prices = PriceRepository(db)
        self.fundamentals = FundamentalsRepository(db)
        self.quality_service = QualityService(db)
        self.growth_service = GrowthService(db)
        self.risk_service = RiskService(db)
        self.valuation_service = ValuationService(db)

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

        latest_snapshot_orm = self.fundamentals.get_latest(asset.id)
        latest_snapshot = (
            _to_result(ticker, latest_snapshot_orm) if latest_snapshot_orm is not None else None
        )

        return calculate_conviction_score_v2(
            data,
            quality_result=self.quality_service.evaluate_ticker(ticker),
            growth_result=self.growth_service.evaluate_ticker(ticker),
            risk_result=self.risk_service.evaluate_ticker(ticker),
            valuation_result=self.valuation_service.evaluate_ticker(ticker),
            latest_snapshot=latest_snapshot,
        )
