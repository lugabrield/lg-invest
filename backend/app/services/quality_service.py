"""Serviço de qualidade (Sprint 16 / Fase 2).

Ponte entre o repositório (ORM) e o Quality Engine (puro): busca o
snapshot de fundamentos mais recente de um ativo e devolve a
classificação de qualidade. Nenhum cálculo mora aqui — só orquestração.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.engines.quality.engine import QualityEngine
from backend.app.infrastructure.database.models.fundamental_snapshot import FundamentalSnapshot
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.quality import QualityResult

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


class QualityService:
    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.fundamentals = FundamentalsRepository(db)
        self.engine = QualityEngine()

    def evaluate_ticker(self, ticker: str) -> QualityResult | None:
        """Devolve a classificação de qualidade de um ativo, ou `None` se
        o ativo não estiver cadastrado."""
        asset = self.assets.get_by_ticker(ticker)
        if asset is None:
            return None

        latest_snapshot = self.fundamentals.get_latest(asset.id)
        snapshot_result = (
            _to_result(ticker, latest_snapshot) if latest_snapshot is not None else None
        )
        return self.engine.evaluate(ticker, asset.asset_class, snapshot_result)
