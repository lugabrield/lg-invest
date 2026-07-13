"""Serviço da Adequação de Carteira — ETF/BTC/Tesouro (Sprint 26, Fase 5).

Ponte entre o `TargetAllocationService` (já existente, Sprint 24) e o
`PortfolioAdequacyEngine` (puro): busca a avaliação de regras v2 já
calculada para o portfólio, filtra pela dimensão "asset" (ticker) e
"class" (classe do ativo) e devolve a adequação. Nenhum cálculo de peso
mora aqui — só orquestração (mesmo padrão de `valuation_v2_service.py`).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.engines.portfolio_adequacy.engine import PortfolioAdequacyEngine
from backend.app.infrastructure.repositories.asset_repository import AssetRepository
from backend.app.schemas.portfolio_adequacy import PortfolioAdequacyResult
from backend.app.schemas.target_allocation import AllocationRuleEvaluation
from backend.app.services.target_allocation_service import TargetAllocationService


class PortfolioAdequacyService:
    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.target_allocation_service = TargetAllocationService(db)
        self.engine = PortfolioAdequacyEngine()

    def evaluate_ticker(self, ticker: str, portfolio_id: int) -> PortfolioAdequacyResult | None:
        """Devolve a adequação de um ativo (ETF/cripto/Tesouro) à política
        de alocação do portfólio, ou `None` se o ativo não estiver
        cadastrado."""
        asset = self.assets.get_by_ticker(ticker)
        if asset is None:
            return None

        evaluation = self.target_allocation_service.evaluate_portfolio_rules(portfolio_id)

        asset_evaluation = self._find(evaluation.evaluations, "asset", ticker)
        class_evaluation = self._find(evaluation.evaluations, "class", asset.asset_class)

        return self.engine.evaluate(
            ticker=ticker,
            asset_class=asset.asset_class,
            asset_evaluation=asset_evaluation,
            class_evaluation=class_evaluation,
        )

    @staticmethod
    def _find(
        evaluations: list[AllocationRuleEvaluation], dimension_type: str, dimension_key: str
    ) -> AllocationRuleEvaluation | None:
        for item in evaluations:
            if item.dimension_type == dimension_type and item.dimension_key == dimension_key:
                return item
        return None
