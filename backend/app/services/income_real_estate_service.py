"""Serviço da Análise de Renda Imobiliária (Sprint 26, Fase 4).

Ponte entre os repositórios (ORM) e o `IncomeRealEstateEngine` (puro):
busca o histórico de fundamentos do ativo e devolve a análise de
P/VP + DY + estabilidade. Nenhum cálculo mora aqui — só orquestração
(mesmo padrão de `valuation_v2_service.py`).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.engines.income_real_estate.engine import IncomeRealEstateEngine
from backend.app.infrastructure.database.models.fundamental_snapshot import FundamentalSnapshot
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.income_real_estate import IncomeRealEstateAnalysisResult

# Mesmos campos de backend/app/services/fundamentals_service.py::_SNAPSHOT_FIELDS
# — duplicado deliberadamente (mesma convenção usada pelos outros serviços que
# consomem snapshots de fundamentos).
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
    "market_cap",
    "enterprise_value",
    "forward_pe",
    "operating_margin",
    "total_debt",
    "total_cash",
    "operating_cash_flow",
    "gross_profit",
    "shares_outstanding",
    "total_equity",
    "roic",
    "interest_coverage",
)


def _to_result(ticker: str, snapshot: FundamentalSnapshot) -> FundamentalSnapshotResult:
    return FundamentalSnapshotResult(
        ticker=ticker,
        period_end=snapshot.period_end,
        source=snapshot.source,
        collected_at=snapshot.updated_at,
        **{field: getattr(snapshot, field) for field in _SNAPSHOT_FIELDS},
    )


class IncomeRealEstateService:
    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.fundamentals = FundamentalsRepository(db)
        self.engine = IncomeRealEstateEngine()

    def evaluate_ticker(self, ticker: str) -> IncomeRealEstateAnalysisResult | None:
        """Devolve a análise de FII/REIT de um ativo, ou `None` se o
        ativo não estiver cadastrado."""
        asset = self.assets.get_by_ticker(ticker)
        if asset is None:
            return None

        raw_history = self.fundamentals.list_by_asset(asset.id)
        history = sorted(
            (_to_result(ticker, snapshot) for snapshot in raw_history),
            key=lambda s: s.period_end,
        )
        latest_snapshot = history[-1] if history else None

        return self.engine.evaluate(
            ticker=ticker,
            asset_class=asset.asset_class,
            latest_snapshot=latest_snapshot,
            history=history,
        )
