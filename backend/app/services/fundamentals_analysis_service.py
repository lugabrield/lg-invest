"""Serviço de análise de fundamentos (Sprint 14 / Fase 2).

Ponte entre o repositório (ORM) e o Fundamentals Engine (puro): busca
os snapshots de um ativo, converte para o schema de entrada do engine
e devolve o resultado. Nenhum cálculo mora aqui — só orquestração.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.engines.fundamentals.engine import FundamentalsEngine
from backend.app.infrastructure.database.models.fundamental_snapshot import FundamentalSnapshot
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.fundamentals_analysis import FundamentalsAnalysisResult

# Mesmos campos de backend/app/services/fundamentals_service.py::_SNAPSHOT_FIELDS
# — duplicado deliberadamente para este serviço não depender de símbolo
# interno de outro serviço (mesma convenção usada na UI de Ativos).
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


class FundamentalsAnalysisService:
    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.fundamentals = FundamentalsRepository(db)
        self.engine = FundamentalsEngine()

    def analyze_ticker(self, ticker: str) -> FundamentalsAnalysisResult | None:
        """Devolve a análise de fundamentos de um ativo, ou `None` se o
        ativo não estiver cadastrado (ausência de snapshots é tratada
        pelo próprio engine, não aqui)."""
        asset = self.assets.get_by_ticker(ticker)
        if asset is None:
            return None

        snapshots = self.fundamentals.list_by_asset(asset.id)
        results = [_to_result(ticker, snapshot) for snapshot in snapshots]
        return self.engine.analyze(ticker, results)
