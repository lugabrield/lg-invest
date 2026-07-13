"""Serviço do Valuation Engine 2.0 (Sprint 26, Fase 2).

Ponte entre os repositórios (ORM) e o Valuation Engine 2.0 (puro): busca
o histórico completo de fundamentos, o preço atual e a classificação de
qualidade de um ativo, roda o Fundamentals Engine para obter CAGR de
FCF/lucro/receita, e devolve a faixa de valor justo. Nenhum cálculo de
valuation mora aqui — só orquestração (mesmo padrão de
`valuation_service.py`, `quality_service.py`).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.engines.fundamentals.engine import FundamentalsEngine
from backend.app.engines.quality.engine import QualityEngine
from backend.app.engines.valuation_v2.engine import ValuationEngineV2
from backend.app.infrastructure.database.models.fundamental_snapshot import FundamentalSnapshot
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.infrastructure.repositories.fundamentals_repository import (
    FundamentalsRepository,
)
from backend.app.infrastructure.repositories.price_repository import PriceRepository
from backend.app.schemas.fundamentals import FundamentalSnapshotResult
from backend.app.schemas.valuation_v2 import ValuationV2Result

# Mesmos campos de backend/app/services/fundamentals_service.py::_SNAPSHOT_FIELDS
# — duplicado deliberadamente (mesma convenção usada pelos outros serviços que
# consomem snapshots de fundamentos). Inclui total_equity/roic/interest_coverage
# (Sprint 26, Fase 1) — total_equity vira valor patrimonial por ação, usado por
# Graham e pelos múltiplos normalizados.
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


class ValuationServiceV2:
    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.fundamentals = FundamentalsRepository(db)
        self.prices = PriceRepository(db)
        self.fundamentals_engine = FundamentalsEngine()
        self.quality_engine = QualityEngine()
        self.engine = ValuationEngineV2()

    def evaluate_ticker(self, ticker: str) -> ValuationV2Result | None:
        """Devolve a faixa de valor justo (Valuation Engine 2.0) de um
        ativo, ou `None` se o ativo não estiver cadastrado."""
        asset = self.assets.get_by_ticker(ticker)
        if asset is None:
            return None

        raw_history = self.fundamentals.list_by_asset(asset.id)
        history = sorted(
            (_to_result(ticker, snapshot) for snapshot in raw_history),
            key=lambda s: s.period_end,
        )
        latest_snapshot = history[-1] if history else None

        latest_price = self.prices.get_latest(asset.id)
        current_price = latest_price.close if latest_price is not None else None

        fundamentals_analysis = (
            self.fundamentals_engine.analyze(ticker, history) if history else None
        )

        quality_result = self.quality_engine.evaluate(ticker, asset.asset_class, latest_snapshot)

        return self.engine.evaluate(
            ticker=ticker,
            asset_class=asset.asset_class,
            currency=asset.currency,
            current_price=current_price,
            latest_snapshot=latest_snapshot,
            history=history,
            fundamentals_analysis=fundamentals_analysis,
            quality_classification=quality_result.classification,
        )
