"""Serviço do Data Coverage Report (Sprint 28).

Ponte entre os repositórios (ORM) e o Data Coverage Engine (puro): busca
o histórico completo de fundamentos e o preço de um ativo, roda o
Fundamentals Engine para obter os CAGRs (mesma peça já usada por
`valuation_v2_service.py`), e devolve o relatório de cobertura. Nenhum
cálculo de cobertura mora aqui — só orquestração.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.engines.data_coverage.engine import DataCoverageEngine
from backend.app.engines.fundamentals.engine import FundamentalsEngine
from backend.app.infrastructure.database.models.fundamental_snapshot import FundamentalSnapshot
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.infrastructure.repositories.price_repository import PriceRepository
from backend.app.schemas.data_coverage import DataCoverageResult
from backend.app.schemas.fundamentals import FundamentalSnapshotResult

# Mesma lista de `valuation_v2_service.py::_SNAPSHOT_FIELDS` — duplicada
# deliberadamente (convenção já estabelecida entre os serviços que
# consomem snapshots de fundamentos), inclui os 30 campos completos
# (Sprint 21 + Sprint 26, Fase 1).
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


class DataCoverageService:
    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.fundamentals = FundamentalsRepository(db)
        self.prices = PriceRepository(db)
        self.fundamentals_engine = FundamentalsEngine()
        self.engine = DataCoverageEngine()

    def evaluate_ticker(self, ticker: str) -> DataCoverageResult | None:
        """Devolve o Data Coverage Report de um ativo, ou `None` se o
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

        fundamentals_analysis = (
            self.fundamentals_engine.analyze(ticker, history) if history else None
        )

        price_history = self.prices.list_by_asset(asset.id)
        latest_price = price_history[-1] if price_history else None

        return self.engine.evaluate(
            ticker=ticker,
            asset_class=asset.asset_class,
            latest_snapshot=latest_snapshot,
            history=history,
            fundamentals_analysis=fundamentals_analysis,
            has_current_price=latest_price is not None,
            price_history_periods=len(price_history),
        )
