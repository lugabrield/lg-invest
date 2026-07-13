"""Serviço do Trap Detection Engine (Sprint 26, Fases 3-4).

Ponte entre os repositórios (ORM) e o Trap Detection Engine (puro):
busca o histórico de fundamentos do ativo, roda o Fundamentals Engine
para CAGR/tendências e, dependendo da classe do ativo, reaproveita o
`ValuationServiceV2` (ações — crescimento implícito via reverse DCF) ou
o `IncomeRealEstateService` (FIIs/REITs — média histórica de DY) antes
de devolver os flags de armadilha. Nenhuma lógica de detecção mora
aqui — só orquestração (mesmo padrão de `valuation_v2_service.py`).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.engines.fundamentals.engine import FundamentalsEngine
from backend.app.engines.trap_detection.engine import TrapDetectionEngine
from backend.app.infrastructure.database.models.fundamental_snapshot import FundamentalSnapshot
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.trap_detection import TrapDetectionResult
from backend.app.services.income_real_estate_service import IncomeRealEstateService
from backend.app.services.valuation_v2_service import ValuationServiceV2

_INCOME_REAL_ESTATE_ASSET_CLASSES = ("fii", "reit")

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


class TrapDetectionService:
    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.fundamentals = FundamentalsRepository(db)
        self.fundamentals_engine = FundamentalsEngine()
        self.valuation_service = ValuationServiceV2(db)
        self.income_real_estate_service = IncomeRealEstateService(db)
        self.engine = TrapDetectionEngine()

    def evaluate_ticker(self, ticker: str) -> TrapDetectionResult | None:
        """Devolve os flags de armadilha de valuation de um ativo, ou
        `None` se o ativo não estiver cadastrado."""
        asset = self.assets.get_by_ticker(ticker)
        if asset is None:
            return None

        raw_history = self.fundamentals.list_by_asset(asset.id)
        history = sorted(
            (_to_result(ticker, snapshot) for snapshot in raw_history),
            key=lambda s: s.period_end,
        )
        latest_snapshot = history[-1] if history else None

        if asset.asset_class in _INCOME_REAL_ESTATE_ASSET_CLASSES:
            income_real_estate = self.income_real_estate_service.evaluate_ticker(ticker)
            return self.engine.evaluate(
                ticker=ticker,
                asset_class=asset.asset_class,
                latest_snapshot=latest_snapshot,
                fundamentals_analysis=None,
                valuation=None,
                income_real_estate=income_real_estate,
            )

        fundamentals_analysis = (
            self.fundamentals_engine.analyze(ticker, history) if history else None
        )

        valuation = self.valuation_service.evaluate_ticker(ticker)

        return self.engine.evaluate(
            ticker=ticker,
            asset_class=asset.asset_class,
            latest_snapshot=latest_snapshot,
            fundamentals_analysis=fundamentals_analysis,
            valuation=valuation,
        )
